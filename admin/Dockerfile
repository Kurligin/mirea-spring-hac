FROM node:20-alpine AS build
WORKDIR /workspace
COPY design/ ./design/
WORKDIR /workspace/admin
COPY admin/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY admin/ ./
RUN npm run build

FROM nginx:1.25-alpine AS runtime
COPY --from=build /workspace/admin/dist /usr/share/nginx/html
COPY admin/nginx.conf /etc/nginx/conf.d/default.conf
