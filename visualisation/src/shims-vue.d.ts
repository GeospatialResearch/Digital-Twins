/** Shim to allow *.vue files to be read in TypeScript */
declare module '*.vue' {
  import Vue from 'vue'
  export default Vue
}
