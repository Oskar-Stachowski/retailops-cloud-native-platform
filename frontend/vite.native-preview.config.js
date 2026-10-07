import { defineConfig } from "vite";
import base from "./vite.config.js";

// The dedicated CI reader owns this random loopback API port; normal UI keeps its config.
const target = process.env.AI10_NATIVE_API_URL;
if (!/^http:\/\/127\.0\.0\.1:[1-9][0-9]{0,4}$/.test(target || "")) {
  throw new Error("An owned loopback native read API is required.");
}

export default defineConfig({
  ...base,
  preview: {
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
