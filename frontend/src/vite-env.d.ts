/// <reference types="vite/client" />
// Author: 晨星

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
