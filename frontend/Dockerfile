FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# 构建时注入高德Web端(JS API) Key,否则前端地图无法初始化
ARG VITE_AMAP_WEB_JS_KEY
ENV VITE_AMAP_WEB_JS_KEY=$VITE_AMAP_WEB_JS_KEY

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
