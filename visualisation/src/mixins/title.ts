// Mixin to append title of a component to the base title of the app and makes this the document title.
// Best to only use this once per page.

import Vue from "vue";

/** The base title of the application, displayed in the document title */
export const appBaseTitle = "Digital Twin for Flood Resilience";

export default {
  /**
   * Changes the document title prefix to the page title
   */
  created: function (this: Vue): void {
    const pageTitle = this.$options.title;
    if (pageTitle) {
      document.title = `${pageTitle} | ${appBaseTitle}`;
    }
  }
};
