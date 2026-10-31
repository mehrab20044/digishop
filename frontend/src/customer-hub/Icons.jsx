export default function HubIcon({ name = "user", size = 22 }) {
  const paths = {
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
      </>
    ),
    orders: (
      <>
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 4V2h6v2M9 10h6M9 15h6" />
      </>
    ),
    heart: (
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
    ),
    later: (
      <>
        <path d="M6 3h12v19l-6-4-6 4Z" />
      </>
    ),
    pin: (
      <>
        <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z" />
        <circle cx="12" cy="10" r="2.5" />
      </>
    ),
    shield: (
      <>
        <path d="m12 2 8 3v6c0 6-8 11-8 11S4 17 4 11V5Z" />
        <path d="m8 11 3 3 5-6" />
      </>
    ),
    payment: (
      <>
        <rect x="2" y="4" width="20" height="16" rx="3" />
        <path d="M2 9h20M6 15h4" />
      </>
    ),
    truck: (
      <>
        <path d="M2 5h12v12H2ZM14 9h4l4 5v3h-8" />
        <circle cx="6" cy="18" r="2" />
        <circle cx="18" cy="18" r="2" />
      </>
    ),
    return: (
      <>
        <path d="M3 4v6h6M3 10a9 9 0 1 1 1 8" />
      </>
    ),
    logout: (
      <>
        <path d="M9 3H3v18h6M12 12h10m-4-4 4 4-4 4" />
      </>
    ),
    box: (
      <>
        <path d="m12 2 9 5v10l-9 5-9-5V7Zm0 10v10M3 7l9 5 9-5M7 5l9 5" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.user}
    </svg>
  );
}
