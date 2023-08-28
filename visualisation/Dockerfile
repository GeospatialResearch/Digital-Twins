# syntax=docker/dockerfile:1

FROM node:lts as build-stage

WORKDIR /app
# Install node_modules
COPY package*.json ./
RUN npm ci
COPY ./ .

# Build code for production style server
RUN npm run build

FROM nginx:stable as production-stage

# Serve built files using nginx
RUN mkdir /app
COPY --from=build-stage /app/dist /app
COPY nginx.conf /etc/nginx/nginx.conf

# Expose nginx web-server on http port (80)
EXPOSE 80
