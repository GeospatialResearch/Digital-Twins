// Adds additional type information for pages
import Vue from 'vue';

// Type augmentation on the Vue options API
declare module 'vue/types/options' {
  /* eslint-disable @typescript-eslint/no-unused-vars */ // Matching V extends Vue with type we are augmenting.
  interface ComponentOptions<V extends Vue> {
    /** Title option for a page, can be used with the title mixin */
    title?: string
  }
}
