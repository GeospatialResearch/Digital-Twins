// Composable to append title of a component to the base title of the app and makes this the document title.

/** The base title of the application, displayed in the document title */
export const appBaseTitle = "Flood Resilience Digital Twin (FReDT)";

import {onMounted} from "vue";

/**
 * Changes the webpage/document title prefix to the page title.
 */
export function usePageTitlePrefix(pageTitle: string) {
  onMounted(() => {
    if (pageTitle) {
      document.title = `${pageTitle} | ${appBaseTitle}`;
    } else {
      document.title = appBaseTitle;
    }
  });
}
