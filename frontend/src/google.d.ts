export {}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string
            callback: (response: { credential: string }) => void
          }) => void
          renderButton: (element: HTMLElement | null, options: Record<string, string | number>) => void
          cancel?: () => void
        }
      }
    }
    __driveboardGoogleInitialized?: boolean
  }
}
