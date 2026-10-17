export function getViewportInfo() {
  return {
    screen: `${window.screen.width} × ${window.screen.height}`,
    available: `${window.screen.availWidth} × ${window.screen.availHeight}`,
    viewport: `${window.innerWidth} × ${window.innerHeight}`,
    devicePixelRatio: window.devicePixelRatio,
    physicalViewport: `${Math.round(window.innerWidth * window.devicePixelRatio)} × ${Math.round(window.innerHeight * window.devicePixelRatio)}`,
  };
}
