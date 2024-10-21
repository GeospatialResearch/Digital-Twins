FROM node:lts AS build-stage

WORKDIR /app
# Install node_modules
COPY visualisation/package*.json ./
RUN npm ci --ignore-scripts

# Copy License file into image root
COPY ./LICENSE ../LICENSE
# Copy visualisation source files into image
COPY ["visualisation/*.ts", "visualisation/*.json", "visualisation/.env.production", "visualisation/index.html", "./"]
COPY visualisation/src/ src/
COPY visualisation/public/ public/

# Build code for production style server
RUN npm run build

FROM nginx:stable AS production-stage

# Serve built files using nginx
RUN mkdir /app
COPY --from=build-stage /app/dist /app
COPY visualisation/nginx.conf /etc/nginx/nginx.conf

COPY visualisation/entrypoint.sh /entrypoint.sh
RUN chmod +x entrypoint.sh

# Expose nginx web-server on http port (80)
EXPOSE 80

# Run entrypoint script for initialising environment variables before starting server
ENTRYPOINT ["/entrypoint.sh"]
