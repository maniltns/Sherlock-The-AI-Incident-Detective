# frontend/Dockerfile
FROM nginx:stable-alpine

COPY static /usr/share/nginx/html
# small tweak: disable logging buffering for simplicity
RUN sed -i 's/access_log/# access_log/g' /etc/nginx/nginx.conf || true

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
