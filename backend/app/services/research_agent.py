from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.schemas.research import (
    AgentStep,
    ClaimScore,
    ConfidenceBreakdown,
    DepthMode,
    ReportSection,
    ResearchMode,
    ResearchReport,
    SourceItem,
)
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.groq_client import GroqClient
from backend.app.services.research_context import ContextChunk


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResearchAgent:
    def __init__(self, groq_client: GroqClient, embedding_service: EmbeddingService) -> None:
        self.groq_client = groq_client
        self.embedding_service = embedding_service

    async def run(
        self,
        *,
        session_id: str,
        query: str,
        mode: ResearchMode,
        depth: DepthMode,
        chunks: list[ContextChunk],
    ) -> tuple[ResearchReport, list[AgentStep], bool]:
        steps: list[AgentStep] = []
        degraded = False

        step = self._step("search", "running", "Searching evidence corpus.")
        steps.append(step)
        ranked_sources = self._rank_chunks(query, chunks, depth)
        step.status = "completed"
        step.summary = f"Ranked {len(ranked_sources)} evidence chunks."
        step.finished_at = utcnow()
        step.payload = {"sources": [source.source_id for source in ranked_sources]}

        browse_step = self._step("browse", "running", "Browsing top evidence sources.")
        steps.append(browse_step)
        shortlisted = ranked_sources[: self._depth_limit(depth)]
        dashboard_source = self._find_source(ranked_sources, "dashboard_visible_state")
        if dashboard_source and not self._find_source(shortlisted, "dashboard_visible_state"):
            shortlisted = [dashboard_source, *shortlisted[: max(self._depth_limit(depth) - 1, 0)]]
        browse_step.status = "completed"
        browse_step.summary = f"Selected {len(shortlisted)} evidence sources."
        browse_step.finished_at = utcnow()
        browse_step.payload = {"titles": [source.title for source in shortlisted]}

        extract_step = self._step("extract", "running", "Extracting structured evidence.")
        steps.append(extract_step)
        evidence_digest = "\n".join(
            f"[{source.source_id}] {source.title}: {source.snippet}" for source in shortlisted
        )
        extract_step.status = "completed"
        extract_step.summary = "Prepared evidence digest for synthesis."
        extract_step.finished_at = utcnow()
        extract_step.payload = {"digest_preview": evidence_digest[:700]}

        analyze_step = self._step("analyze", "running", "Analyzing evidence and contradictions.")
        steps.append(analyze_step)
        llm_payload = await self.groq_client.structured_completion(
            system_prompt=(
                "You are an air-quality intelligence agent. "
                "Return JSON with keys overview, sections, follow_ups, contradictions, claims, "
                "confidence, and title. Sections must be an array of objects with key, title, content, and sources."
            ),
            user_prompt=(
                f"Mode: {mode}\nDepth: {depth}\nQuery: {query}\n"
                f"Evidence:\n{evidence_digest}\n"
                "Use only the provided evidence. Be explicit about uncertainty. "
                "Confidence must include overall, data_quality, coverage, reasoning_strength as 0-1 floats."
            ),
        )
        analyze_step.finished_at = utcnow()
        if llm_payload is None:
            analyze_step.status = "partial"
            analyze_step.summary = "Groq synthesis unavailable, falling back to deterministic report."
            degraded = True
        else:
            analyze_step.status = "completed"
            analyze_step.summary = "Groq synthesis completed."
            analyze_step.payload = {"title": llm_payload.get("title")}

        summarize_step = self._step("summarize", "running", "Preparing structured report.")
        steps.append(summarize_step)
        report = self._compose_report(
            session_id=session_id,
            query=query,
            mode=mode,
            depth=depth,
            llm_payload=llm_payload,
            sources=shortlisted,
            degraded=degraded,
        )
        summarize_step.status = "completed"
        summarize_step.summary = "Structured report assembled."
        summarize_step.finished_at = utcnow()
        summarize_step.payload = {"report_id": report.report_id}

        score_step = self._step("score", "running", "Scoring report confidence.")
        steps.append(score_step)
        score_step.status = "completed"
        score_step.summary = f"Overall confidence {report.confidence.overall:.2f}."
        score_step.finished_at = utcnow()

        final_step = self._step("final", "completed", "Final response ready.")
        final_step.finished_at = utcnow()
        steps.append(final_step)
        return report, steps, degraded

    def _compose_report(
        self,
        *,
        session_id: str,
        query: str,
        mode: ResearchMode,
        depth: DepthMode,
        llm_payload: dict | None,
        sources: list[SourceItem],
        degraded: bool,
    ) -> ResearchReport:
        if llm_payload:
            sections = [
                ReportSection(
                    key=section.get("key", f"section-{index}"),
                    title=section.get("title", f"Section {index + 1}"),
                    content=section.get("content", ""),
                    sources=section.get("sources", []),
                )
                for index, section in enumerate(llm_payload.get("sections", []))
            ]
            claims = [
                ClaimScore(
                    claim=claim.get("claim", ""),
                    confidence=float(claim.get("confidence", 0.5)),
                    supporting_sources=claim.get("supporting_sources", []),
                    contradiction_sources=claim.get("contradiction_sources", []),
                )
                for claim in llm_payload.get("claims", [])
            ]
            confidence = llm_payload.get("confidence", {})
            breakdown = ConfidenceBreakdown(
                overall=float(confidence.get("overall", 0.74)),
                data_quality=float(confidence.get("data_quality", 0.78)),
                coverage=float(confidence.get("coverage", 0.72)),
                reasoning_strength=float(confidence.get("reasoning_strength", 0.75)),
            )
            overview = llm_payload.get("overview", "")
            follow_ups = llm_payload.get("follow_ups", [])
            contradictions = llm_payload.get("contradictions", [])
            title = llm_payload.get("title", f"{mode.title()} research")
        else:
            (
                title,
                overview,
                sections,
                claims,
                follow_ups,
                contradictions,
                breakdown,
            ) = self._compose_fallback_report(query=query, mode=mode, sources=sources)

        summary_markdown = self._markdown(title, overview, sections, follow_ups, contradictions, breakdown, degraded)
        return ResearchReport(
            report_id=str(uuid.uuid4()),
            session_id=session_id,
            query=query,
            title=title,
            mode=mode,
            depth=depth,
            overview=overview,
            sections=sections,
            follow_ups=follow_ups,
            sources=sources,
            claims=claims,
            contradictions=contradictions,
            confidence=breakdown,
            summary_markdown=summary_markdown,
            created_at=utcnow(),
        )

    def _compose_fallback_report(
        self,
        *,
        query: str,
        mode: ResearchMode,
        sources: list[SourceItem],
    ) -> tuple[
        str,
        str,
        list[ReportSection],
        list[ClaimScore],
        list[str],
        list[str],
        ConfidenceBreakdown,
    ]:
        # The local fallback uses grounded evidence snippets to keep producing a usable
        # air-quality brief even when the remote synthesis layer is unavailable.
        dashboard = self._find_source(sources, "dashboard_visible_state")
        live = self._find_source(sources, "live_station")
        forecast = self._find_source(sources, "forecast_station")
        alerts = self._find_source(sources, "alerts")
        network = self._find_source(sources, "live_network")
        history = self._find_source(sources, "historical_recent")
        dataset = self._find_source(sources, "dataset_summary")

        dashboard_meta = dashboard.metadata or {} if dashboard else {}
        live_meta = live.metadata or {} if live else {}
        history_meta = history.metadata or {} if history else {}
        forecast_meta = forecast.metadata or {} if forecast else {}
        alerts_meta = alerts.metadata or {} if alerts else {}
        network_meta = network.metadata or {} if network else {}
        dataset_meta = dataset.metadata or {} if dataset else {}
        network_top = list(network_meta.get("top_locations", [])) if isinstance(network_meta.get("top_locations"), list) else []
        network_city = (
            str(dashboard_meta.get("selected_city_label") or dashboard_meta.get("selected_city_name"))
            if dashboard_meta.get("selected_city_label") or dashboard_meta.get("selected_city_name")
            else self._city_label(network_top[0]) if network_top else "the live network"
        )

        o3_now = self._num(dashboard_meta.get("visible_o3")) or self._num(live_meta.get("o3"))
        no2_now = self._num(dashboard_meta.get("visible_no2")) or self._num(live_meta.get("no2"))
        o3_avg = self._num(history_meta.get("avg_o3"))
        no2_avg = self._num(history_meta.get("avg_no2"))
        o3_peak = self._num(dashboard_meta.get("forecast_peak_o3")) or self._num(forecast_meta.get("peak_o3"))
        no2_peak = self._num(dashboard_meta.get("forecast_peak_no2")) or self._num(forecast_meta.get("peak_no2"))
        peak_o3_hour = self._hour_label(dashboard_meta.get("forecast_peak_o3_time"), forecast_meta.get("peak_o3_hour"))
        peak_no2_hour = self._hour_label(dashboard_meta.get("forecast_peak_no2_time"), forecast_meta.get("peak_no2_hour"))
        alert_count = int(dashboard_meta.get("alert_count") if dashboard_meta.get("alert_count") is not None else alerts_meta.get("count") or 0)

        clean_query = self._clean_query(query)
        risk_state = self._risk_label(o3_peak or o3_now or 0, no2_peak or no2_now or 0)
        intent = self._intent(clean_query)
        title = self._title_for_intent(intent, mode)

        station_delta_o3 = None if o3_now is None or o3_avg is None else o3_now - o3_avg
        station_delta_no2 = None if no2_now is None or no2_avg is None else no2_now - no2_avg
        situation = (
            f"The current station reading shows O3 at {self._fmt(o3_now)} ug/m3 and NO2 at {self._fmt(no2_now)} ug/m3. "
            f"The recent SIH-derived station baseline is O3 {self._fmt(o3_avg)} ug/m3 and NO2 {self._fmt(no2_avg)} ug/m3. "
            f"That puts O3 {self._signed(station_delta_o3)} ug/m3 versus baseline and NO2 {self._signed(station_delta_no2)} ug/m3 versus baseline."
        )
        outlook = (
            f"The {dashboard_meta.get('horizon_hours', 24)}-hour forecast peaks at O3 {self._fmt(o3_peak)} ug/m3 around {peak_o3_hour} "
            f"and NO2 {self._fmt(no2_peak)} ug/m3 around {peak_no2_hour}. "
            f"The displayed forecast should be read as a live-anchored horizon, not as the raw historical timestamp used inside the training/unseen files."
        )
        top_city = network_top[0] if network_top else {}
        city_o3 = self._num(top_city.get("o3")) if top_city else None
        city_no2 = self._num(top_city.get("no2")) if top_city else None
        city_aqi = self._num(top_city.get("us_aqi")) if top_city else None
        network_context = (
            f"The top live-network comparison point is {network_city}, with O3 {self._fmt(city_o3)} ug/m3, "
            f"NO2 {self._fmt(city_no2)} ug/m3, and modeled US AQI estimate {self._fmt(city_aqi)}. "
            f"Against the selected station, that is O3 {self._signed(None if city_o3 is None or o3_now is None else city_o3 - o3_now)} "
            f"and NO2 {self._signed(None if city_no2 is None or no2_now is None else city_no2 - no2_now)}."
        )
        actions = (
            f"{'There are active threshold signals in the configured alert layer.' if alert_count else 'There are no active configured threshold exceedance alerts right now.'} "
            f"Watch the lead-hour window around the higher of the two pollutant peaks, and compare it with the live-network hotspot before calling the risk isolated."
        )
        alert_driver, alert_driver_claim = self._alert_driver(
            o3_now=o3_now,
            no2_now=no2_now,
            o3_avg=o3_avg,
            no2_avg=no2_avg,
            o3_peak=o3_peak,
            no2_peak=no2_peak,
            peak_o3_hour=peak_o3_hour,
            peak_no2_hour=peak_no2_hour,
            alerts_meta=alerts_meta,
            dashboard_meta=dashboard_meta,
        )
        dataset_context = (
            f"The supervised model is grounded in {int(dataset_meta.get('total_train_rows') or 0):,} SIH training rows across "
            f"{int(dataset_meta.get('total_sites') or 0)} sites, with targets {', '.join(dataset_meta.get('targets') or [])}. "
            f"Live API readings are used as current context and auxiliary evidence, while the trained target behavior comes from the SIH O3/NO2 labels."
        )
        unknowns = (
            "This run used local synthesis because the remote Groq generation path was unavailable or not configured. "
            "The answer still uses project data, but contradiction handling and free-form reasoning are narrower than the Groq path."
        )

        comparison_section, comparison_overview, comparison_claims = self._comparison_from_query(
            query=clean_query,
            network_top=network_top,
            station_o3=o3_now,
            station_no2=no2_now,
            station_label=str(dashboard_meta.get("station_label") or "Selected station"),
        )

        overview = comparison_overview if intent == "comparison" else (
            f"For this query, I used the dashboard-visible station state, SIH station dataset, forecast artifacts, "
            f"alert rules, and the {network_meta.get('scope', 'live')} city network. Visible station values are "
            f"O3 {self._fmt(o3_now)} ug/m3 and NO2 {self._fmt(no2_now)} ug/m3; the next-24h forecast state is {risk_state.lower()}."
        )

        section_map = {
            "situation": ReportSection(key="situation", title="Station Reading vs SIH Baseline", content=situation, sources=self._source_ids(dashboard, live, history)),
            "outlook": ReportSection(key="outlook", title="Next-24h Forecast Window", content=outlook, sources=self._source_ids(dashboard, forecast, alerts)),
            "network": comparison_section or ReportSection(key="network", title="Station vs Live City Network", content=network_context, sources=self._source_ids(dashboard, network, live)),
            "actions": ReportSection(key="actions", title="Operator Takeaway", content=actions, sources=self._source_ids(forecast, alerts, network)),
            "alert": ReportSection(key="alert", title="Alert Driver", content=alert_driver, sources=self._source_ids(dashboard, alerts, forecast, live, history)),
            "dataset": ReportSection(key="dataset", title="Dataset and Training Grounding", content=dataset_context, sources=self._source_ids(dataset, forecast)),
            "unknowns": ReportSection(key="unknowns", title="Reliability Notes", content=unknowns, sources=self._source_ids(dataset, forecast)),
        }
        sections = self._sections_for_intent(intent, section_map)
        claims = comparison_claims if intent == "comparison" else [
            ClaimScore(
                claim=f"Current station O3 is {self._fmt(o3_now)} ug/m3 and NO2 is {self._fmt(no2_now)} ug/m3.",
                confidence=0.84,
                supporting_sources=self._source_ids(dashboard, live),
            ),
            alert_driver_claim,
            ClaimScore(
                claim=f"Next-24h peak O3 is {self._fmt(o3_peak)} ug/m3 and peak NO2 is {self._fmt(no2_peak)} ug/m3.",
                confidence=0.8,
                supporting_sources=self._source_ids(forecast),
            ),
            ClaimScore(
                claim=f"Regional context currently points to {network_city} as a useful live comparison city.",
                confidence=0.72,
                supporting_sources=self._source_ids(network),
            ),
        ]
        follow_ups = [
            self._follow_up_for_intent(intent, "primary"),
            "Compare the selected station with the current live-network hotspot.",
            "Explain which SIH dataset fields are most relevant to this answer.",
        ]
        contradictions = [
            "No strong contradiction detection was available in local synthesis mode; verify any policy-critical conclusion against the source cards."
        ]
        breakdown = ConfidenceBreakdown(
            overall=0.73,
            data_quality=0.82,
            coverage=0.76,
            reasoning_strength=0.65,
        )
        return title, overview, sections, claims, follow_ups, contradictions, breakdown

    def _rank_chunks(self, query: str, chunks: list[ContextChunk], depth: DepthMode) -> list[SourceItem]:
        score_values = self.embedding_service.similarity_scores(query, [chunk.text for chunk in chunks])
        items = [
            SourceItem(
                source_id=chunk.chunk_id,
                title=chunk.title,
                source_type=chunk.source_type,
                snippet=chunk.text[:480],
                credibility=chunk.credibility,
                url=chunk.url,
                cluster=self._cluster(chunk.source_type, chunk.credibility),
                agreement="supports",
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]
        ranked = [
            (source, score_values[index] + source.credibility * 0.25)
            for index, source in enumerate(items)
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        limit = 6 if depth == "quick" else 10 if depth == "standard" else 14
        return [item[0] for item in ranked[:limit]]

    @staticmethod
    def _find_source(sources: list[SourceItem], source_id: str) -> SourceItem | None:
        return next((source for source in sources if source.source_id == source_id), None)

    @staticmethod
    def _extract_pollutants(text: str) -> dict[str, float]:
        values: dict[str, float] = {}
        import re

        o3_match = re.search(r"O3(?: is| at)?\s+([0-9]+(?:\.[0-9]+)?)", text)
        no2_match = re.search(r"NO2(?: is| at)?\s+([0-9]+(?:\.[0-9]+)?)", text)
        avg_o3_match = re.search(r"Average O3 is\s+([0-9]+(?:\.[0-9]+)?)", text)
        avg_no2_match = re.search(r"average NO2 is\s+([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if o3_match:
            values["o3"] = float(o3_match.group(1))
        if no2_match:
            values["no2"] = float(no2_match.group(1))
        if avg_o3_match:
            values["avg_o3"] = float(avg_o3_match.group(1))
        if avg_no2_match:
            values["avg_no2"] = float(avg_no2_match.group(1))
        return values

    @staticmethod
    def _extract_forecast(text: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        import re

        peak_o3_match = re.search(r"Peak O3 is\s+([0-9]+(?:\.[0-9]+)?)\s+ug/m3 at\s+([0-9T:\-+.]+)", text)
        peak_no2_match = re.search(r"Peak NO2 is\s+([0-9]+(?:\.[0-9]+)?)\s+ug/m3 at\s+([0-9T:\-+.]+)", text)
        if peak_o3_match:
            values["peak_o3"] = float(peak_o3_match.group(1))
            values["peak_o3_time"] = peak_o3_match.group(2)
        if peak_no2_match:
            values["peak_no2"] = float(peak_no2_match.group(1))
            values["peak_no2_time"] = peak_no2_match.group(2)
        return values

    @staticmethod
    def _source_ids(*items: SourceItem | None) -> list[str]:
        return [item.source_id for item in items if item is not None]

    def _comparison_from_query(
        self,
        *,
        query: str,
        network_top: list[dict[str, Any]],
        station_o3: float | None,
        station_no2: float | None,
        station_label: str,
    ) -> tuple[ReportSection | None, str | None, list[ClaimScore]]:
        if not network_top:
            return None, None, []

        hotspot = network_top[0]
        hotspot_label = self._city_label(hotspot)
        hotspot_o3 = self._num(hotspot.get("o3"))
        hotspot_no2 = self._num(hotspot.get("no2"))
        hotspot_aqi = self._num(hotspot.get("us_aqi"))

        named_city = self._find_city_in_query(query, network_top)
        named_label = self._city_label(named_city) if named_city else station_label
        named_o3 = self._num(named_city.get("o3")) if named_city else station_o3
        named_no2 = self._num(named_city.get("no2")) if named_city else station_no2
        named_aqi = self._num(named_city.get("us_aqi")) if named_city else None

        if named_label == hotspot_label:
            overview = (
                f"{named_label} is itself the current hotspot in the live network. "
                f"It is currently showing O3 {self._fmt(named_o3)} ug/m3, NO2 {self._fmt(named_no2)} ug/m3, and modeled US AQI estimate {self._fmt(hotspot_aqi)}."
            )
            section = ReportSection(
                key="network",
                title="Requested City vs Current Hotspot",
                content=(
                    f"The requested city and the current hotspot are the same location: {hotspot_label}. "
                    f"There is no second city to compare against until the hotspot ranking changes."
                ),
                sources=["live_network"],
            )
            claims = [
                ClaimScore(
                    claim=f"{hotspot_label} is currently the highest ranked live-network city in this scope.",
                    confidence=0.8,
                    supporting_sources=["live_network"],
                )
            ]
            return section, overview, claims

        stronger_o3 = hotspot_label if (hotspot_o3 or 0) > (named_o3 or 0) else named_label
        stronger_no2 = hotspot_label if (hotspot_no2 or 0) > (named_no2 or 0) else named_label
        overview = (
            f"Comparing {named_label} with the current global hotspot {hotspot_label}: "
            f"{hotspot_label} is higher on modeled US AQI estimate, while pollutant leadership splits across O3 and NO2 depending on the pair."
        )
        section = ReportSection(
            key="network",
            title=f"{named_label} vs {hotspot_label}",
            content=(
                f"{named_label} currently shows O3 {self._fmt(named_o3)} ug/m3, NO2 {self._fmt(named_no2)} ug/m3"
                f"{'' if named_aqi is None else f', and modeled US AQI estimate {self._fmt(named_aqi)}'}. "
                f"{hotspot_label} currently shows O3 {self._fmt(hotspot_o3)} ug/m3, NO2 {self._fmt(hotspot_no2)} ug/m3, and modeled US AQI estimate {self._fmt(hotspot_aqi)}. "
                f"Relative to {named_label}, {hotspot_label} is O3 {self._signed(None if hotspot_o3 is None or named_o3 is None else hotspot_o3 - named_o3)} "
                f"and NO2 {self._signed(None if hotspot_no2 is None or named_no2 is None else hotspot_no2 - named_no2)}. "
                f"That means O3 is currently stronger in {stronger_o3}, while NO2 is stronger in {stronger_no2}."
            ),
            sources=["live_network"],
        )
        claims = [
            ClaimScore(
                claim=f"{hotspot_label} currently exceeds {named_label} on modeled US AQI estimate and remains the hotspot in this live-network scope.",
                confidence=0.82,
                supporting_sources=["live_network"],
            ),
            ClaimScore(
                claim=f"O3 and NO2 can point to different leaders between {named_label} and {hotspot_label}.",
                confidence=0.76,
                supporting_sources=["live_network"],
            ),
        ]
        return section, overview, claims

    def _alert_driver(
        self,
        *,
        o3_now: float | None,
        no2_now: float | None,
        o3_avg: float | None,
        no2_avg: float | None,
        o3_peak: float | None,
        no2_peak: float | None,
        peak_o3_hour: str,
        peak_no2_hour: str,
        alerts_meta: dict[str, Any],
        dashboard_meta: dict[str, Any],
    ) -> tuple[str, ClaimScore]:
        active_alerts = list(alerts_meta.get("items", [])) if isinstance(alerts_meta.get("items"), list) else []
        if active_alerts:
            highest = max(active_alerts, key=lambda item: self._num(item.get("value")) or 0)
            pollutant = str(highest.get("pollutant") or "the configured pollutant")
            content = (
                f"The active alert layer is being driven by {pollutant}. "
                f"Its reported value is {self._fmt(self._num(highest.get('value')))} ug/m3 against a threshold of "
                f"{self._fmt(self._num(highest.get('threshold')))} ug/m3, with severity {highest.get('severity', 'unknown')}. "
                f"Use that pollutant as the lead signal, then check whether the forecast peak keeps rising in the next 24 hours."
            )
            claim = ClaimScore(
                claim=f"{pollutant} is the active configured alert driver.",
                confidence=0.86,
                supporting_sources=["alerts", "forecast_station", "live_station"],
                contradiction_sources=[],
            )
            return content, claim

        o3_live_delta = None if o3_now is None or o3_avg is None else o3_now - o3_avg
        no2_live_delta = None if no2_now is None or no2_avg is None else no2_now - no2_avg
        o3_pressure = max(o3_peak or 0, o3_now or 0)
        no2_pressure = max(no2_peak or 0, no2_now or 0)
        if abs(no2_live_delta or 0) > abs(o3_live_delta or 0):
            driver = "NO2"
            reason = (
                f"NO2 is farther from its recent SIH baseline: {self._signed(no2_live_delta)} ug/m3 versus "
                f"O3 {self._signed(o3_live_delta)} ug/m3. "
            )
        elif o3_pressure >= no2_pressure:
            driver = "O3"
            reason = (
                f"O3 has the stronger forecast pressure, peaking at {self._fmt(o3_peak)} ug/m3 around {peak_o3_hour}, "
                f"while NO2 peaks at {self._fmt(no2_peak)} ug/m3 around {peak_no2_hour}. "
            )
        else:
            driver = "NO2"
            reason = (
                f"NO2 has the stronger current/forecast pressure, peaking at {self._fmt(no2_peak)} ug/m3 around {peak_no2_hour}, "
                f"while O3 peaks at {self._fmt(o3_peak)} ug/m3 around {peak_o3_hour}. "
            )

        visible_state = (
            f"The dashboard-visible point is {dashboard_meta.get('station_label', 'the selected station')} "
            f"at {dashboard_meta.get('selected_label', dashboard_meta.get('selected_timestamp', 'the selected moment'))}. "
            if dashboard_meta
            else ""
        )
        content = (
            f"No configured threshold alert is active right now, so there is no formal alert driver. "
            f"If this is treated as a watch question, {driver} is the pollutant to watch first. "
            f"{visible_state}{reason}"
            f"Current values are O3 {self._fmt(o3_now)} ug/m3 and NO2 {self._fmt(no2_now)} ug/m3."
        )
        claim = ClaimScore(
            claim=f"{driver} is the current watch driver, but no configured alert is active.",
            confidence=0.78,
            supporting_sources=["alerts", "forecast_station", "live_station", "historical_recent"],
            contradiction_sources=[],
        )
        return content, claim

    @staticmethod
    def _intent(query: str) -> str:
        normalized = query.lower()
        if any(term in normalized for term in ["alert", "threshold", "warning", "critical", "risk", "drives the alert", "driving the alert"]):
            return "alert"
        if any(term in normalized for term in ["dataset", "training", "trained", "features", "columns", "data"]):
            return "dataset"
        if any(term in normalized for term in ["compare", "city", "global", "india", "network", "hotspot"]):
            return "comparison"
        if any(term in normalized for term in ["forecast", "future", "next", "24", "peak", "spike"]):
            return "forecast"
        if any(term in normalized for term in ["why", "anomaly", "rise", "rising", "drop", "high", "low"]):
            return "diagnostic"
        return "brief"

    @staticmethod
    def _clean_query(query: str) -> str:
        return query.split("\n\nContext:")[0].strip()

    @staticmethod
    def _title_for_intent(intent: str, mode: ResearchMode) -> str:
        titles = {
            "dataset": "Dataset grounding brief",
            "comparison": "Station and city-network comparison",
            "forecast": "Short-term forecast brief",
            "alert": "Alert and risk brief",
            "diagnostic": "Pollutant behavior diagnosis",
            "brief": f"{mode.title()} intelligence brief",
        }
        return titles.get(intent, titles["brief"])

    @staticmethod
    def _sections_for_intent(intent: str, section_map: dict[str, ReportSection]) -> list[ReportSection]:
        order_by_intent = {
            "dataset": ["dataset", "situation", "outlook", "unknowns"],
            "comparison": ["network", "actions", "unknowns"],
            "forecast": ["outlook", "situation", "actions", "unknowns"],
            "alert": ["alert", "outlook", "actions", "situation"],
            "diagnostic": ["situation", "outlook", "network", "dataset", "unknowns"],
            "brief": ["situation", "outlook", "network", "actions", "unknowns"],
        }
        return [section_map[key] for key in order_by_intent.get(intent, order_by_intent["brief"])]

    @staticmethod
    def _follow_up_for_intent(intent: str, slot: str) -> str:
        del slot
        followups = {
            "dataset": "Show which training features and targets are being used for the selected station.",
            "comparison": "Rank the selected station against the top three live-network cities.",
            "forecast": "Explain whether the forecast peak is ozone-led, NO2-led, or mixed.",
            "alert": "Check whether current alert thresholds are too strict or too loose for this forecast.",
            "diagnostic": "Explain the likely driver of the pollutant movement using weather and recent history.",
            "brief": "Summarize what an operator should watch in the next 6 to 12 hours.",
        }
        return followups.get(intent, followups["brief"])

    @staticmethod
    def _city_label(city: object) -> str:
        if not isinstance(city, dict):
            return "the live network"
        name = city.get("name") or "Unknown city"
        country = city.get("country") or ""
        return f"{name}, {country}".strip().strip(",")

    @staticmethod
    def _find_city_in_query(query: str, cities: list[dict[str, Any]]) -> dict[str, Any] | None:
        normalized = query.lower()
        ranked = sorted(cities, key=lambda city: len(str(city.get("name") or "")), reverse=True)
        for city in ranked:
            name = str(city.get("name") or "").lower()
            country = str(city.get("country") or "").lower()
            if name and name in normalized:
                return city
            if country and f"{name}, {country}" in normalized:
                return city
        return None

    @staticmethod
    def _num(value: object) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _hour_label(visible_time: object, lead_hour: object) -> str:
        if visible_time:
            return str(visible_time)
        if lead_hour:
            return f"lead hour +{lead_hour}"
        return "n/a"

    @staticmethod
    def _risk_label(o3: float, no2: float) -> str:
        if o3 >= 140 or no2 >= 110:
            return "High risk"
        if o3 >= 95 or no2 >= 70:
            return "Elevated"
        return "Stable"

    @staticmethod
    def _fmt(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "n/a"

    @staticmethod
    def _signed(value: float | None) -> str:
        if value is None:
            return "n/a"
        sign = "+" if value >= 0 else ""
        return f"{sign}{value:.1f}"

    @staticmethod
    def _cluster(source_type: str, credibility: float) -> str:
        if credibility >= 0.9:
            return f"{source_type}-high"
        if credibility >= 0.75:
            return f"{source_type}-medium"
        return f"{source_type}-exploratory"

    @staticmethod
    def _depth_limit(depth: DepthMode) -> int:
        return {"quick": 4, "standard": 6, "deep": 9}[depth]

    @staticmethod
    def _step(name: str, status: str, summary: str) -> AgentStep:
        return AgentStep(
            step_id=str(uuid.uuid4()),
            name=name,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            started_at=utcnow(),
            finished_at=None,
            payload=None,
        )

    @staticmethod
    def _markdown(
        title: str,
        overview: str,
        sections: list[ReportSection],
        follow_ups: list[str],
        contradictions: list[str],
        confidence: ConfidenceBreakdown,
        degraded: bool,
    ) -> str:
        lines = [f"# {title}", "", overview, ""]
        if degraded:
            lines.extend(["**Synthesis status:** degraded fallback mode", ""])
        for section in sections:
            lines.extend([f"## {section.title}", section.content, ""])
        lines.extend(["## Follow-ups", *[f"- {item}" for item in follow_ups], ""])
        lines.extend(["## Contradictions", *[f"- {item}" for item in contradictions], ""])
        lines.extend(
            [
                "## Confidence",
                json.dumps(confidence.model_dump(), indent=2),
            ]
        )
        return "\n".join(lines)
