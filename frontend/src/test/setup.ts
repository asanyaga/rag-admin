import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// @testing-library/dom's waitFor checks `typeof jest !== 'undefined'` before it
// uses `Object.prototype.hasOwnProperty.call(setTimeout, 'clock')` to detect
// @sinonjs/fake-timers (which Vitest uses). Without this shim the library never
// enters its fake-timer path and the polling setInterval is left frozen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
;(globalThis as any).jest = {
  advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms),
}

afterEach(() => {
  cleanup()
})

// happy-dom's MutationObserver errors when observe/disconnect are called without
// the internal window symbol set. Zone.js (from @opentelemetry/context-zone) then
// wraps MutationObserver via patchClass(), which uses `for...in` to enumerate the
// original instance's methods and copy them to its wrapper prototype. Class
// prototype methods are non-enumerable, so Zone.js's wrapper ends up with no
// observe/disconnect — causing "x is not a function" errors in waitFor and Radix UI.
//
// Fix: replace MutationObserver with a no-op whose prototype methods are enumerable
// so Zone.js's for...in discovers them and delegates to the no-ops.
class _NoopMutationObserver {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_callback: MutationCallback) {}
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  observe(_target: Node, _options?: MutationObserverInit): void {}
  disconnect(): void {}
  takeRecords(): MutationRecord[] {
    return []
  }
}
// Make prototype methods enumerable so Zone.js's `for (prop in instance)` finds them.
const _noopObserverMethods = ['observe', 'disconnect', 'takeRecords']
_noopObserverMethods.forEach((m) =>
  Object.defineProperty(_NoopMutationObserver.prototype, m, { enumerable: true }),
)
global.MutationObserver = _NoopMutationObserver as unknown as typeof MutationObserver

// Polyfill ResizeObserver for happy-dom (used by Radix UI Slider etc.)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Radix UI Select/Dropdown rely on pointer capture + scrollIntoView, absent in
// happy-dom. Guard with typeof so node-environment tests (e.g. @vitest-environment
// node) don't crash on `Element is not defined`.
if (typeof Element !== 'undefined') {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {}
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {}
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {}
  }
}
