FROM nginx:1.27-alpine

COPY apps/voice-client/index.html apps/voice-client/styles.css apps/voice-client/app.js apps/voice-client/config.js /usr/share/nginx/html/
COPY docker/voice-client/docker-entrypoint.sh /docker-entrypoint.d/99-lala-config.sh
RUN chmod +x /docker-entrypoint.d/99-lala-config.sh

EXPOSE 80
