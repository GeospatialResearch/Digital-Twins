// Mixin to append title of a component to the base title of the app and makes this the document title.
// Best to only use this once per page.

import type {App} from "vue";

/** The base title of the application, displayed in the document title */
export const appBaseTitle = "Flood Resilience Digital Twin (FReDT)";

export default {
  /**
   * Changes the document title prefix to the page title
   */
  created: function (this: App): void {
    const pageTitle = this.$options.title;
    if (pageTitle) {
      document.title = `${pageTitle} | ${appBaseTitle}`;
    }
  }
};
