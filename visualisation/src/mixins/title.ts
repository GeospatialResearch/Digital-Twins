// Mixin to append name of component to name of app and makes this the webpage title

import Vue, {ComponentOptions} from "vue";

export default {
  /**
   * Changes the document title if a component has a data variable `title`
   */
  created: function (this: Vue): void {
    const pageTitle = getPageTitle(this);
    if (pageTitle) {
      const mainTitle = "Digital Twin for Flood Resilience";
      document.title = `${pageTitle} | ${mainTitle}`;
    }
  }
}

/** Gets data variable title from page */
function getPageTitle(vm: Vue): string | undefined {
  const {title} = vm.$options as ComponentOptions<Vue> & { title?: string } // Optional title variable added to component
  return title;
}
