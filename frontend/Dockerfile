# Development image for the existing Next.js application.
FROM node:22-bookworm-slim

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

COPY --chown=node:node package.json ./
RUN chown -R node:node /app
USER node

# No committed npm lockfile yet; add one and switch this to npm ci later.
RUN npm install --no-audit --no-fund

COPY --chown=node:node . ./
# .next is a named volume; allow the host-matching dev user to write to it.
RUN mkdir -p .next && chmod 0777 .next

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
