import react from "eslint-plugin-react";
import globals from "globals";

export default [{
  files: ["frontend/**/*.{js,jsx}", "e2e/**/*.js", "vite.config.js", "playwright.config.js"],
  languageOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    globals: { ...globals.browser, ...globals.node },
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
  plugins: { react },
  settings: { react: { version: "detect" } },
  rules: {
    "react/jsx-uses-vars": "error",
    "react/jsx-uses-react": "error",
    "no-unused-vars": ["error", {
      argsIgnorePattern: "^_",
      varsIgnorePattern: "^_",
      caughtErrors: "none",
      ignoreRestSiblings: true,
    }],
  },
}];
