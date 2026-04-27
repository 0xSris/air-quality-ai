FROM node:20-alpine

WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

