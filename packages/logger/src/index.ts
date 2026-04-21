/**
 * SiteGuard 日志工具
 */

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error',
  CRITICAL = 'critical'
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, any>;
  error?: Error;
}

export interface LoggerOptions {
  level?: LogLevel;
  format?: 'json' | 'text';
  timestampFormat?: string;
  enableConsole?: boolean;
  enableFile?: boolean;
  filePath?: string;
  maxFileSize?: number;
  maxFiles?: number;
}

export class Logger {
  private options: Required<LoggerOptions>;
  private logQueue: LogEntry[] = [];

  constructor(options: LoggerOptions = {}) {
    this.options = {
      level: options.level || LogLevel.INFO,
      format: options.format || 'text',
      timestampFormat: options.timestampFormat || 'YYYY-MM-DD HH:mm:ss',
      enableConsole: options.enableConsole ?? true,
      enableFile: options.enableFile ?? false,
      filePath: options.filePath || 'logs/siteguard.log',
      maxFileSize: options.maxFileSize || 10 * 1024 * 1024, // 10MB
      maxFiles: options.maxFiles || 5
    };
  }

  debug(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.DEBUG, message, context);
  }

  info(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.INFO, message, context);
  }

  warn(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.WARN, message, context);
  }

  error(message: string, error?: Error, context?: Record<string, any>): void {
    this.log(LogLevel.ERROR, message, context, error);
  }

  critical(message: string, error?: Error, context?: Record<string, any>): void {
    this.log(LogLevel.CRITICAL, message, context, error);
  }

  private log(
    level: LogLevel,
    message: string,
    context?: Record<string, any>,
    error?: Error
  ): void {
    // 检查日志级别
    if (!this.shouldLog(level)) {
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      error
    };

    // 添加到队列
    this.logQueue.push(entry);

    // 输出到控制台
    if (this.options.enableConsole) {
      this.outputToConsole(entry);
    }

    // 输出到文件
    if (this.options.enableFile) {
      this.outputToFile(entry);
    }

    // 限制队列大小
    if (this.logQueue.length > 1000) {
      this.logQueue = this.logQueue.slice(-500);
    }
  }

  private shouldLog(level: LogLevel): boolean {
    const levels = {
      [LogLevel.DEBUG]: 0,
      [LogLevel.INFO]: 1,
      [LogLevel.WARN]: 2,
      [LogLevel.ERROR]: 3,
      [LogLevel.CRITICAL]: 4
    };

    return levels[level] >= levels[this.options.level];
  }

  private outputToConsole(entry: LogEntry): void {
    const timestamp = new Date(entry.timestamp).toLocaleString();
    const level = entry.level.toUpperCase().padEnd(7);
    const message = entry.message;
    const contextStr = entry.context ? ` ${JSON.stringify(entry.context)}` : '';
    const errorStr = entry.error ? `\n${entry.error.stack || entry.error.message}` : '';

    const colors = {
      [LogLevel.DEBUG]: '\x1b[36m', // Cyan
      [LogLevel.INFO]: '\x1b[32m',  // Green
      [LogLevel.WARN]: '\x1b[33m',  // Yellow
      [LogLevel.ERROR]: '\x1b[31m', // Red
      [LogLevel.CRITICAL]: '\x1b[41m\x1b[37m' // Red background, white text
    };

    const reset = '\x1b[0m';
    const color = colors[entry.level] || reset;

    console.log(`${color}[${timestamp}] ${level} ${message}${contextStr}${errorStr}${reset}`);
  }

  private outputToFile(entry: LogEntry): void {
    // 文件输出需要Node.js环境
    if (typeof window !== 'undefined') {
      return;
    }

    try {
      const fs = require('fs');
      const path = require('path');

      // 确保目录存在
      const dir = path.dirname(this.options.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      let output: string;
      if (this.options.format === 'json') {
        output = JSON.stringify(entry) + '\n';
      } else {
        const timestamp = new Date(entry.timestamp).toLocaleString();
        const level = entry.level.toUpperCase().padEnd(7);
        const message = entry.message;
        const contextStr = entry.context ? ` ${JSON.stringify(entry.context)}` : '';
        const errorStr = entry.error ? ` ERROR: ${entry.error.message}` : '';
        output = `[${timestamp}] ${level} ${message}${contextStr}${errorStr}\n`;
      }

      // 检查文件大小
      if (fs.existsSync(this.options.filePath)) {
        const stats = fs.statSync(this.options.filePath);
        if (stats.size > this.options.maxFileSize) {
          this.rotateLogFile();
        }
      }

      // 追加到文件
      fs.appendFileSync(this.options.filePath, output, 'utf8');
    } catch (error) {
      console.error('文件日志记录失败:', error);
    }
  }

  private rotateLogFile(): void {
    try {
      const fs = require('fs');
      const path = require('path');

      for (let i = this.options.maxFiles - 1; i >= 0; i--) {
        const currentFile = i === 0 ? this.options.filePath : `${this.options.filePath}.${i}`;
        const nextFile = `${this.options.filePath}.${i + 1}`;

        if (fs.existsSync(currentFile)) {
          if (i === this.options.maxFiles - 1) {
            // 删除最旧的文件
            fs.unlinkSync(currentFile);
          } else {
            // 重命名文件
            fs.renameSync(currentFile, nextFile);
          }
        }
      }
    } catch (error) {
      console.error('日志文件轮转失败:', error);
    }
  }

  getLogs(count: number = 100): LogEntry[] {
    return this.logQueue.slice(-count);
  }

  clearLogs(): void {
    this.logQueue = [];
  }

  setLevel(level: LogLevel): void {
    this.options.level = level;
  }

  getOptions(): LoggerOptions {
    return { ...this.options };
  }
}

// 创建默认logger实例
export const logger = new Logger();

// 便捷方法
export function debug(message: string, context?: Record<string, any>): void {
  logger.debug(message, context);
}

export function info(message: string, context?: Record<string, any>): void {
  logger.info(message, context);
}

export function warn(message: string, context?: Record<string, any>): void {
  logger.warn(message, context);
}

export function error(message: string, error?: Error, context?: Record<string, any>): void {
  logger.error(message, error, context);
}

export function critical(message: string, error?: Error, context?: Record<string, any>): void {
  logger.critical(message, error, context);
}