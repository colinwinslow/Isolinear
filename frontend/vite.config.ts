import { defineConfig } from "vite";

export default defineConfig({
  build: {
    emptyOutDir: false,
    lib: {
      entry: "src/isolinear-card.ts",
      fileName: "isolinear-card",
      formats: ["es"],
    },
    outDir: "dist",
  },
});
