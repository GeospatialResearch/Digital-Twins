FROM node:lts as build-stage

WORKDIR /app
# Install node_modules
COPY visualisation/package*.json ./
RUN npm ci

# Copy License file into image root
COPY ./LICENSE ../LICENSE
# Copy visualisation source files into image
COPY visualisation/ .

# Build code for production style server
RUN npm run build

FROM nginx:stable as production-stage

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
