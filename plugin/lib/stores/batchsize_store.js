'use babel';

import BaseStore from './base_store';
import Throughput from '../models/Throughput';
import Memory from '../models/Memory';
import {
  evaluateLinearModel,
  getBatchSizeFromUsage,
  getBatchSizeFromThroughput,
} from '../utils';
import INNPVStore from './innpv_store';
import {Range} from 'atom';

class BatchSizeStore extends BaseStore {
  constructor() {
    super();
    this._throughputInfo = null;
    this._memoryInfo = null;
    this._inputInfo = null;

    this._predictedBatchSize = null;
    this._maxBatchSize = null;

    this._currentAnnotationRange = null;
    this._currentUndoCheckpoint = null;
  }

  receivedAnalysis(throughputInfo, memoryInfo, inputInfo) {
    this._throughputInfo = throughputInfo;
    this._memoryInfo = memoryInfo;
    this._inputInfo = inputInfo;

    this._predictedBatchSize = null;
    this._maxBatchSize = getBatchSizeFromUsage(
      this._memoryInfo.getUsageModelMb(),
      this._memoryInfo.getMaxCapacityMb(),
    );

    const startPoint = this._inputInfo.getAnnotationStart();
    const endPoint = this._inputInfo.getAnnotationEnd();
    this._currentAnnotationRange = new Range(
      [startPoint.getLine(), startPoint.getColumn()],
      [endPoint.getLine(), endPoint.getColumn()],
    );
    this._currentUndoCheckpoint = INNPVStore.getEditor().getBuffer().createCheckpoint();

    this.notifyChanged();
  }

  updateMemoryUsage(deltaPct, basePct) {
    // Map the delta to a usage value
    // NOTE: We clamp the values (upper bound for usage, lower bound for batch size)
    const updatedPct = basePct + deltaPct;
    const updatedUsage = Math.min(
      updatedPct / 100 * this._memoryInfo.getMaxCapacityMb(),
      this._memoryInfo.getMaxCapacityMb(),
    );
    this._predictedBatchSize = Math.max(
      getBatchSizeFromUsage(this._memoryInfo.getUsageModelMb(), updatedUsage),
      1,
    );

    this._updateAnnotationInBuffer();
    this.notifyChanged();
  }

  updateThroughput(deltaPct, basePct) {
    // Map the delta to a throughput value
    // NOTE: We clamp the values (upper bound for throughput, lower bound for batch size)
    const updatedPct = basePct + deltaPct;
    const updatedThroughput = Math.max(Math.min(
      updatedPct / 100 * this._throughputInfo.getMaxThroughput(),
      this._throughputInfo.getThroughputLimit(),
    ), 0);
    const throughputBatchSize = getBatchSizeFromThroughput(
      this._throughputInfo.getRuntimeModelMs(),
      updatedThroughput,
    );

    if (throughputBatchSize < 0) {
      // NOTE: The throughput batch size may be so large that it overflows
      this._predictedBatchSize = this._maxBatchSize;
    } else {
      this._predictedBatchSize = Math.max(Math.min(throughputBatchSize, this._maxBatchSize), 1);
    }

    this._updateAnnotationInBuffer();
    this.notifyChanged();
  }

  _updateAnnotationInBuffer() {
    const buffer = INNPVStore.getEditor().getBuffer();
    const updatedAnnotation = this._getAnnotationString();
    INNPVStore.ignoreEditorChanges();
    this._currentAnnotationRange = buffer.setTextInRange(
      this._currentAnnotationRange,
      updatedAnnotation,
    );
    buffer.groupChangesSinceCheckpoint(this._currentUndoCheckpoint);
    INNPVStore.subscribeToEditorChanges();
  }

  _getAnnotationString() {
    const inputSizeTuple = this._inputInfo.getInputSize().getValuesList();
    const inputSizeCopy = inputSizeTuple.map(x => x);
    if (this._predictedBatchSize != null) {
      inputSizeCopy[0] = Math.round(this._predictedBatchSize);
    }
    return `@innpv size (${inputSizeCopy.join(', ')})`;
  }

  clearPredictions() {
    this._predictedBatchSize = null;
    this._updateAnnotationInBuffer();
    this.notifyChanged();
  }

  getThroughputModel() {
    if (this._throughputInfo == null) {
      return null;
    }

    if (this._predictedBatchSize == null) {
      return Throughput.fromInfo(this._throughputInfo);
    } else {
      return Throughput.fromPrediction(this._throughputInfo, this._predictedBatchSize);
    }
  }

  getMemoryModel() {
    if (this._memoryInfo == null) {
      return null;
    }

    if (this._predictedBatchSize == null) {
      return Memory.fromInfo(this._memoryInfo);
    } else {
      return Memory.fromPrediction(this._memoryInfo, this._predictedBatchSize);
    }
  }

  getInputInfo() {
    return this._inputInfo;
  }
}

const storeInstance = new BatchSizeStore();

export default storeInstance;
