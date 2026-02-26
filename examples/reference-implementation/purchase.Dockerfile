FROM node:20-alpine

WORKDIR /app

COPY packages/sdk-js /app/packages/sdk-js
COPY examples/purchase-target /app/examples/purchase-target

WORKDIR /app/packages/sdk-js
RUN npm install
RUN npm run build

WORKDIR /app/examples/purchase-target
RUN npm install

EXPOSE 3002
