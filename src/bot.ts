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
      if ('sendTyping' in message.channel) {
        await message.channel.sendTyping();
      }

      // Download the audio file
      const response = await fetch(voiceAttachment.url);
      const audioBuffer = Buffer.from(await response.arrayBuffer());

      // Transcribe it
      taskDescription = await transcribeAudio(audioBuffer, voiceAttachment.name || 'audio.ogg');
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

  try {
    // Show typing indicator
    if ('sendTyping' in message.channel) {
      await message.channel.sendTyping();
    }

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

    // Send the combined response
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
