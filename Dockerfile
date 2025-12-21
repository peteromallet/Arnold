# Use Node.js LTS
FROM node:20-slim

# Install git and other dependencies
RUN apt-get update && apt-get install -y \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user for security (required for Claude Code bypassPermissions)
RUN useradd -m -s /bin/bash arnold
RUN mkdir -p /tmp/workspace && chown arnold:arnold /tmp/workspace

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci

# Copy source files
COPY tsconfig.json ./
COPY src ./src

# Build TypeScript
RUN npm run build

# Remove devDependencies to slim down
RUN npm prune --production

# Change ownership to arnold user
RUN chown -R arnold:arnold /app

# Switch to non-root user
USER arnold

# Set environment
ENV NODE_ENV=production

# Start the bot
CMD ["node", "dist/bot.js"]
