import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

/**
 * The one piece of this app that touches the DOM directly — and it does it
 * exactly once. frontend/app.js calls document.querySelector(...) and
 * mutates elements throughout its ~150KB; here, this single render() call
 * hands React the #root element and React owns everything inside it from
 * this point on. No other file in src/ ever calls document.* itself.
 */
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
