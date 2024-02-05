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

COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x entrypoint.sh

# Expose nginx web-server on http port (80)
EXPOSE 80

# Run entrypoint script for initialising environment variables before starting server
ENTRYPOINT ["/entrypoint.sh"]
