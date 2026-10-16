import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend chạy ở http://localhost:5173, backend ở http://localhost:8000 (đã bật CORS).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
