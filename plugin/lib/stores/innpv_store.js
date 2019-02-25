'use babel';

import EventEmitter from 'events';

import AppState from '../models/AppState';

const UPDATE_EVENT = 'updated';

class INNPVStore {
  constructor() {
    this._appState = AppState.ACTIVATED;

    this._emitter = new EventEmitter();
  }

  getAppState() {
    return this._appState;
  }

  setAppState(state) {
    this._appState = state;
    this._notifyChanged();
  }

  addListener(callback) {
    this._emitter.on(UPDATE_EVENT, callback);
  }

  removeListener(callback) {
    this._emitter.removeListener(UPDATE_EVENT, callback);
  }

  _notifyChanged() {
    this._emitter.emit(UPDATE_EVENT);
  }
}

const storeInstance = new INNPVStore();

export default storeInstance;