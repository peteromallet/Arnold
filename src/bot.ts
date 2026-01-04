import { Client, GatewayIntentBits, Events, Partials, Message, TextChannel } from 'discord.js';
import { config } from './config.js';
import { logger } from './logger.js';
import { toUserMessage } from './errors.js';
import { parseTask } from './agent.js';
import { transcribeAudio, isTranscriptionAvailable } from './transcribe.js';
import { executor } from './executor.js';
import type { ConversationMessage, NotifyCallback } from './types.js';

// Store the last channel used for notifications
let notifyChannel: TextChannel | null = null;

/**
 * Natural typing indicator that simulates human-like typing behavior
 * - Starts after a random delay (0.5-2s)
 * - Randomly pauses and resumes
 * - Stops when stop() is called
 */
class NaturalTypingIndicator {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private channel: any;
  private running = false;
  private timeoutId: NodeJS.Timeout | null = null;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  constructor(channel: any) {
    this.channel = channel;
  }

  /**
   * Start the typing indicator immediately
   */
  start(): void {
    if (this.running) return;
    this.running = true;
    
    // Start typing immediately - no initial delay
    this.typeLoop();
  }

  /**
   * Stop the typing indicator
   */
  stop(): void {
    this.running = false;
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  /**
   * Internal typing loop with random pauses
   */
  private async typeLoop(): Promise<void> {
    if (!this.running) return;

    // Send typing indicator if channel supports it
    if (typeof this.channel?.sendTyping === 'function') {
      try {
        await this.channel.sendTyping();
      } catch {
        // Ignore errors (channel might be unavailable)
      }
    }

    if (!this.running) return;

    // Random behavior: 70% chance to continue typing, 30% chance to pause
    const shouldPause = Math.random() < 0.3;
    
    if (shouldPause) {
      // Pause for 1-3 seconds, then resume
      const pauseDuration = 1000 + Math.random() * 2000;
      this.timeoutId = setTimeout(() => this.typeLoop(), pauseDuration);
    } else {
      // Continue typing - Discord typing lasts ~10s, so refresh every 5-8s
      const typingDuration = 5000 + Math.random() * 3000;
      this.timeoutId = setTimeout(() => this.typeLoop(), typingDuration);
    }
  }
}

/**
 * Run an async operation with natural typing indicator
 */
async function withTypingIndicator<T>(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  channel: any,
  operation: () => Promise<T>,
): Promise<T> {
  const typing = new NaturalTypingIndicator(channel);
  typing.start();
  try {
    return await operation();
  } finally {
    typing.stop();
  }
}

/**
 * Get the current notify callback (uses last active channel)
 */
function getNotifyCallback(): NotifyCallback {
  return (msg: string) => {
    if (notifyChannel) {
      notifyChannel.send(msg).catch((err) => logger.error('Failed to send notification', err));
    } else {
      logger.info('Notification (no channel)', { message: msg });
    }
  };
}

// Create Discord client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
  ],
  partials: [Partials.Channel, Partials.Message],
});

/**
 * Check if an attachment is a voice note
 */
function isVoiceAttachment(attachment: { contentType?: string | null; name?: string | null }): boolean {
  return !!(
    attachment.contentType?.startsWith('audio/') ||
    attachment.name?.endsWith('.ogg') ||
    attachment.name?.endsWith('.mp3') ||
    attachment.name?.endsWith('.m4a') ||
    attachment.name?.endsWith('.wav')
  );
}

/**
 * Fetch conversation history from a channel
 */
async function fetchConversationHistory(
  message: Message,
  limit: number = 10,
): Promise<ConversationMessage[]> {
  try {
    const messages = await message.channel.messages.fetch({ limit: limit + 1 });
    const previousMessages = [...messages.values()]
      .filter((m) => m.id !== message.id)
      .slice(0, limit)
      .reverse();

    return previousMessages.map((msg) => {
      let content = msg.content;

      // Check for voice attachments and note them
      const hasVoice = msg.attachments.some((att) => isVoiceAttachment(att));
      if (hasVoice && !content) {
        content = '[voice note - content unknown]';
      }

      const isBot = msg.author.id === message.client.user?.id;
      return {
        role: isBot ? 'assistant' : 'user',
        content: content || '[empty or media message]',
      } as ConversationMessage;
    });
  } catch (error) {
    logger.error('Failed to fetch message history', error instanceof Error ? error : undefined);
    return [];
  }
}

/**
 * Handle incoming messages
 */
async function handleMessage(message: Message): Promise<void> {
  // Ignore bot messages
  if (message.author.bot) return;

  // Check user authorization
  if (config.discord.allowedUserId && message.author.id !== config.discord.allowedUserId) {
    logger.debug('Ignoring unauthorized user', { userId: message.author.id });
    return;
  }

  // Check if message is relevant (DM or has prefix)
  const isDM = !message.guild;
  const startsWithPrefix = message.content.startsWith(config.discord.prefix);

  if (!isDM && !startsWithPrefix) {
    return;
  }

  // Extract task description
  let taskDescription = message.content;
  if (startsWithPrefix) {
    taskDescription = message.content.slice(config.discord.prefix.length).trim();
  }

  // Check for voice note attachments
  const voiceAttachment = message.attachments.find((att) => isVoiceAttachment(att));

  if (voiceAttachment) {
    if (!isTranscriptionAvailable()) {
      await message.reply('❌ Voice notes are not configured (missing GROQ_API_KEY)');
      return;
    }

    logger.info('Voice note detected', {
      filename: voiceAttachment.name,
      contentType: voiceAttachment.contentType,
    });

    try {
      // Transcribe with natural typing indicator
      taskDescription = await withTypingIndicator(message.channel, async () => {
        const response = await fetch(voiceAttachment.url);
        const audioBuffer = Buffer.from(await response.arrayBuffer());
        return transcribeAudio(audioBuffer, voiceAttachment.name || 'audio.ogg');
      });
      logger.info('Voice note transcribed', { preview: taskDescription.substring(0, 50) });
    } catch (error) {
      logger.error('Transcription failed', error instanceof Error ? error : undefined);
      await message.reply(`❌ Couldn't transcribe that voice note: ${toUserMessage(error)}`);
      return;
    }
  }

  if (!taskDescription) {
    await message.reply('Send me a task (text or voice).');
    return;
  }

  // Store notify channel for executor callbacks (updates the global)
  notifyChannel = message.channel as TextChannel;

  // Fetch conversation history
  const conversationHistory = await fetchConversationHistory(message);
  logger.debug('Conversation context loaded', { messageCount: conversationHistory.length });

  // Start typing indicator immediately and keep it running until reply is sent
  const typing = new NaturalTypingIndicator(message.channel);
  typing.start();

  try {
    // Parse and execute with Claude
    logger.info('Processing message', {
      userId: message.author.id,
      preview: taskDescription.substring(0, 50),
    });

    const result = await parseTask(taskDescription, conversationHistory, getNotifyCallback());

    logger.debug('Parse result', { actionsCount: result.actions.length, hasReply: !!result.reply });

    // Build response based on actions taken
    const replyParts: string[] = [];

    for (const action of result.actions) {
      if (action.tool === 'reply' && action.result.success && action.result.message) {
        replyParts.push(action.result.message);
      }
    }

    // If Claude also provided a text reply, add it
    if (result.reply && !result.actions.some((a) => a.tool === 'reply')) {
      replyParts.push(result.reply);
    }

    // Send the combined response (typing indicator still running)
    if (replyParts.length > 0) {
      const finalReply = replyParts.join('\n\n---\n\n');
      // Discord has a 2000 char limit
      if (finalReply.length > 1900) {
        await message.reply(finalReply.substring(0, 1900) + '...');
      } else {
        await message.reply(finalReply);
      }
    } else {
      await message.reply("🤔 Done, but I'm not sure what to say about it!");
    }
  } catch (error) {
    logger.error('Message processing failed', error instanceof Error ? error : undefined, {
      userId: message.author.id,
    });
    await message.reply(`❌ Something went wrong: ${toUserMessage(error)}`);
  } finally {
    // Stop typing indicator after reply is sent
    typing.stop();
  }
}

/**
 * Graceful shutdown handler
 */
async function shutdown(signal: string): Promise<void> {
  logger.info('Shutdown initiated', { signal });

  // Stop accepting new tasks
  try {
    executor.stop();
  } catch {
    // Executor might not be running, that's fine
  }

  // Wait for current task to finish
  try {
    await executor.waitForIdle(config.executor.shutdownTimeoutMs);
  } catch (error) {
    logger.error('Error waiting for executor', error instanceof Error ? error : undefined);
  }

  // Disconnect Discord
  try {
    await client.destroy();
    logger.info('Discord client disconnected');
  } catch (error) {
    logger.error('Error disconnecting Discord', error instanceof Error ? error : undefined);
  }

  logger.info('Shutdown complete');
  process.exit(0);
}

// Register event handlers
client.once(Events.ClientReady, async (c) => {
  logger.info('Bot ready', { tag: c.user.tag });

  if (config.discord.allowedUserId) {
    logger.info('User restriction enabled', { allowedUserId: config.discord.allowedUserId });
  } else {
    logger.warn('No DISCORD_USER_ID set - accepting commands from anyone');
  }

  // Auto-start the executor
  try {
    const result = await executor.start(getNotifyCallback());
    if (result.success) {
      logger.info('Executor auto-started');
    } else {
      logger.error('Failed to auto-start executor', undefined, { message: result.message });
    }
  } catch (error) {
    logger.error('Error auto-starting executor', error instanceof Error ? error : undefined);
  }

  // Send startup notification to allowed user
  if (config.discord.allowedUserId) {
    try {
      const user = await c.users.fetch(config.discord.allowedUserId);
      const dm = await user.createDM();
      await dm.send('🤖 Arnold has relaunched and is ready.');
      logger.info('Sent startup notification');
    } catch (error) {
      logger.error('Failed to send startup notification', error instanceof Error ? error : undefined);
    }
  }
});

client.on(Events.MessageCreate, (message) => {
  handleMessage(message).catch((error) => {
    logger.error('Unhandled error in message handler', error instanceof Error ? error : undefined);
  });
});

// Register shutdown handlers
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception', error);
  shutdown('uncaughtException').catch(() => process.exit(1));
});

process.on('unhandledRejection', (reason) => {
  logger.error('Unhandled rejection', reason instanceof Error ? reason : undefined, {
    reason: String(reason),
  });
});

// Start the bot
logger.info('Starting Arnold', { version: '1.0.0' });
client.login(config.discord.token).catch((error) => {
  logger.error('Failed to login to Discord', error instanceof Error ? error : undefined);
  process.exit(1);
});

