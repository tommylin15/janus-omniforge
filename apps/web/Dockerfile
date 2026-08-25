FROM node:22.14.0-bookworm-slim

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY . .

ENV NODE_ENV=production
ENV PORT=8080
EXPOSE 8080

# The web application entrypoint will be defined with the first implementation.
CMD ["npm", "run", "start"]
