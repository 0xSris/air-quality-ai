import ReactECharts from "echarts-for-react";
import { ForecastPoint, PollutantPoint } from "../types/api";

type TrendChartProps = {
  historical: PollutantPoint[];
  live: PollutantPoint[];
  forecast: ForecastPoint[];
  networkLive: PollutantPoint[];
  pollutantFocus: "both" | "o3" | "no2";
  selectedTimestamp?: string | null;
  onInvestigatePoint?: (point: { timestamp: string; pollutant: "O3" | "NO2"; value: number }) => void;
};

function seriesOpacity(focus: "both" | "o3" | "no2", pollutant: "o3" | "no2") {
  if (focus === "both") return 1;
  return focus === pollutant ? 1 : 0.18;
}

export function TrendChart({
  historical,
  live,
  forecast,
  networkLive,
  pollutantFocus,
  selectedTimestamp,
  onInvestigatePoint,
}: TrendChartProps) {
  const observed = [...historical.slice(-24), ...live.slice(-24)];
  const forecastStart = forecast[0]?.timestamp;
  const forecastEnd = forecast[forecast.length - 1]?.timestamp;
  const baselineO3 = observed.length ? observed.reduce((sum, point) => sum + point.o3, 0) / observed.length : 0;
  const baselineNO2 = observed.length ? observed.reduce((sum, point) => sum + point.no2, 0) / observed.length : 0;
  const anomalyPoints = observed
    .flatMap((point) => [
      point.o3 > Math.max(95, baselineO3 * 1.35)
        ? { timestamp: point.timestamp, pollutant: "O3" as const, value: point.o3 }
        : null,
      point.no2 > Math.max(70, baselineNO2 * 1.35)
        ? { timestamp: point.timestamp, pollutant: "NO2" as const, value: point.no2 }
        : null,
    ])
    .filter(Boolean)
    .slice(-8) as { timestamp: string; pollutant: "O3" | "NO2"; value: number }[];

  const option = {
    backgroundColor: "transparent",
    animationDuration: 900,
    animationEasing: "cubicOut",
    grid: { left: 26, right: 26, top: 34, bottom: 60 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(5, 12, 18, 0.92)",
      borderColor: "rgba(120, 231, 247, 0.16)",
      textStyle: { color: "#ebf7ff" },
      valueFormatter: (value: number) => `${Number(value).toFixed(1)} ug/m3`,
    },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: "rgba(212, 244, 255, 0.12)" } },
      axisTick: { show: false },
      axisLabel: {
        color: "rgba(212, 244, 255, 0.58)",
        margin: 18,
        formatter: (value: number) =>
          new Date(value).toLocaleString(undefined, {
            day: "numeric",
            month: "short",
            hour: "2-digit",
          }),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "rgba(212, 244, 255, 0.54)" },
      splitLine: { lineStyle: { color: "rgba(212, 244, 255, 0.08)" } },
    },
    legend: {
      top: 0,
      right: 12,
      textStyle: { color: "rgba(212, 244, 255, 0.64)" },
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      data: ["O3 live", "NO2 live", "O3 forecast", "NO2 forecast"],
    },
    series: [
      {
        name: "O3 live",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: observed.map((point) => [point.timestamp, point.o3]),
        lineStyle: {
          width: 3.5,
          color: "#69e3ff",
          shadowBlur: 22,
          shadowColor: "rgba(105, 227, 255, 0.32)",
          opacity: seriesOpacity(pollutantFocus, "o3"),
        },
        areaStyle: {
          color: "rgba(105, 227, 255, 0.08)",
          opacity: seriesOpacity(pollutantFocus, "o3") * 0.8,
        },
      },
      {
        name: "NO2 live",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: observed.map((point) => [point.timestamp, point.no2]),
        lineStyle: {
          width: 3,
          color: "#ff8e63",
          shadowBlur: 18,
          shadowColor: "rgba(255, 142, 99, 0.28)",
          opacity: seriesOpacity(pollutantFocus, "no2"),
        },
      },
      {
        name: "O3 forecast floor",
        type: "line",
        showSymbol: false,
        data: forecast.map((point) => [point.timestamp, point.o3_lower]),
        lineStyle: { opacity: 0 },
        stack: "o3-band",
        silent: true,
      },
      {
        name: "O3 forecast",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: forecast.map((point) => [point.timestamp, point.o3]),
        lineStyle: {
          width: 2.5,
          type: "dashed",
          color: "#9cf781",
          opacity: seriesOpacity(pollutantFocus, "o3"),
        },
        itemStyle: { color: "#9cf781" },
      },
      {
        name: "O3 forecast band",
        type: "line",
        showSymbol: false,
        data: forecast.map((point) => [point.timestamp, Math.max(point.o3_upper - point.o3_lower, 0)]),
        lineStyle: { opacity: 0 },
        areaStyle: { color: "rgba(156, 247, 129, 0.14)" },
        stack: "o3-band",
        silent: true,
      },
      {
        name: "NO2 forecast floor",
        type: "line",
        showSymbol: false,
        data: forecast.map((point) => [point.timestamp, point.no2_lower]),
        lineStyle: { opacity: 0 },
        stack: "no2-band",
        silent: true,
      },
      {
        name: "NO2 forecast",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: forecast.map((point) => [point.timestamp, point.no2]),
        lineStyle: {
          width: 2.4,
          type: "dashed",
          color: "#ffb470",
          opacity: seriesOpacity(pollutantFocus, "no2"),
        },
        itemStyle: { color: "#ffb470" },
      },
      {
        name: "NO2 forecast band",
        type: "line",
        showSymbol: false,
        data: forecast.map((point) => [point.timestamp, Math.max(point.no2_upper - point.no2_lower, 0)]),
        lineStyle: { opacity: 0 },
        areaStyle: { color: "rgba(255, 180, 112, 0.12)" },
        stack: "no2-band",
        silent: true,
      },
      {
        name: "Network trace",
        type: "line",
        showSymbol: false,
        smooth: true,
        data: networkLive.slice(-24).map((point) => [point.timestamp, point.o3]),
        lineStyle: {
          width: 1.4,
          type: "dotted",
          color: "rgba(226, 245, 255, 0.42)",
        },
        silent: true,
      },
      {
        name: "Anomaly markers",
        type: "scatter",
        symbolSize: 14,
        data: anomalyPoints.map((point) => [point.timestamp, point.value, point.pollutant]),
        itemStyle: {
          color: (params: { data?: unknown[] }) => (params.data?.[2] === "O3" ? "#69e3ff" : "#ffb470"),
          shadowBlur: 18,
          shadowColor: "rgba(255,255,255,0.32)",
        },
        emphasis: { scale: 1.6 },
        tooltip: {
          formatter: (params: { data?: unknown[] }) =>
            `${params.data?.[2] ?? "Signal"} anomaly<br/>${Number(params.data?.[1] ?? 0).toFixed(1)} ug/m3<br/>Click to investigate`,
        },
      },
    ],
    markArea:
      forecastStart && forecastEnd
        ? {
            silent: true,
            itemStyle: { color: "rgba(110, 247, 210, 0.06)" },
            data: [[{ xAxis: forecastStart }, { xAxis: forecastEnd }]],
          }
        : undefined,
    markLine: selectedTimestamp
      ? {
          silent: true,
          symbol: "none",
          lineStyle: { color: "rgba(255, 255, 255, 0.4)", width: 1, type: "solid" },
          data: [{ xAxis: selectedTimestamp }],
        }
      : undefined,
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 520, width: "100%" }}
      onEvents={{
        click: (params: { seriesName?: string; data?: unknown[] }) => {
          if (params.seriesName !== "Anomaly markers" || !params.data || !onInvestigatePoint) return;
          onInvestigatePoint({
            timestamp: String(params.data[0]),
            value: Number(params.data[1]),
            pollutant: params.data[2] === "NO2" ? "NO2" : "O3",
          });
        },
      }}
    />
  );
}
