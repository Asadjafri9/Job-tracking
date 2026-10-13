globalThis.ExtensionApiOrigin = Object.freeze({
  fromHostPermissions(hostPermissions) {
    const permission = hostPermissions?.[0];
    if (typeof permission !== "string") {
      throw new Error("The extension manifest has no API host permission.");
    }
    const url = new URL(permission.replace(/\/\*$/, "/"));
    if (url.pathname !== "/" || url.search || url.hash) {
      throw new Error("The extension API permission must be an origin wildcard.");
    }
    return url.origin;
  },
});
