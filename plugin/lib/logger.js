'use babel';

import {Logger, LogLevel} from './logger_impl';

const logger = new Logger(LogLevel.DEBUG);

export default logger;