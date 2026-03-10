import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePolling } from './usePolling';

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('calls callback at specified interval when enabled', () => {
    // Arrange
    const callback = vi.fn();

    // Act
    renderHook(() => usePolling(callback, 2000, true));

    vi.advanceTimersByTime(6000);

    // Assert
    expect(callback).toHaveBeenCalledTimes(3);
  });

  it('does not call callback when disabled', () => {
    // Arrange
    const callback = vi.fn();

    // Act
    renderHook(() => usePolling(callback, 2000, false));

    vi.advanceTimersByTime(6000);

    // Assert
    expect(callback).not.toHaveBeenCalled();
  });

  it('stops calling when enabled changes to false', () => {
    // Arrange
    const callback = vi.fn();
    let enabled = true;

    const { rerender } = renderHook(() => usePolling(callback, 2000, enabled));

    vi.advanceTimersByTime(4000);
    expect(callback).toHaveBeenCalledTimes(2);

    // Act
    enabled = false;
    rerender();
    vi.advanceTimersByTime(4000);

    // Assert
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('cleans up interval on unmount', () => {
    // Arrange
    const callback = vi.fn();
    const { unmount } = renderHook(() => usePolling(callback, 2000, true));

    vi.advanceTimersByTime(2000);
    expect(callback).toHaveBeenCalledTimes(1);

    // Act
    unmount();
    vi.advanceTimersByTime(4000);

    // Assert
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('uses latest callback reference', () => {
    // Arrange
    const callback1 = vi.fn();
    const callback2 = vi.fn();
    let cb = callback1;

    const { rerender } = renderHook(() => usePolling(cb, 2000, true));

    vi.advanceTimersByTime(2000);
    expect(callback1).toHaveBeenCalledTimes(1);

    // Act
    cb = callback2;
    rerender();
    vi.advanceTimersByTime(2000);

    // Assert
    expect(callback1).toHaveBeenCalledTimes(1);
    expect(callback2).toHaveBeenCalledTimes(1);
  });
});
