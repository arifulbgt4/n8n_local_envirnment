FROM node:20-alpine
WORKDIR /app
COPY server.mjs ./server.mjs
ENV PORT=3001 CACHE_DIR=/data/product-media MAX_IMAGE_BYTES=26214400 GRAPH_VERSION=v26.0
EXPOSE 3001
CMD ["node", "server.mjs"]
