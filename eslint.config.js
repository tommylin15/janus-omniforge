import js from "@eslint/js";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "test-results/**"]
  },
  js.configs.recommended,
  {
    files: ["**/*.js", "**/*.mjs"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        fetch: "readonly",
        HTMLElement: "readonly",
        HTMLDialogElement: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        console: "readonly"
      }
    },
    rules: {
      "no-unused-vars": ["error", { "args": "none" }]
    }
  }
];
