module.exports = {
    content: ['./src/**/*.{js,jsx}'],
    darkMode: 'class',
    theme: {
      extend: {
        colors: {
          border: 'hsl(var(--border))',
          background: 'hsl(var(--background))',
          foreground: 'hsl(var(--foreground))',
          card: 'hsl(var(--card))',
          muted: {
            DEFAULT: 'hsl(var(--muted))',
            foreground: 'hsl(var(--muted-foreground))',
          },
          primary: {
            DEFAULT: 'hsl(var(--primary))',
            foreground: 'hsl(var(--primary-foreground))',
          },
          secondary: {
            DEFAULT: 'hsl(var(--secondary))',
            foreground: 'hsl(var(--secondary-foreground))',
          },
          success: 'hsl(var(--success))',
          warning: {
            DEFAULT: 'hsl(var(--warning))',
            foreground: 'hsl(var(--warning-foreground))',
          },
          destructive: 'hsl(var(--destructive))',
          ring: 'hsl(var(--ring))',
          input: 'hsl(var(--input))',
          sidebar: {
            DEFAULT: 'hsl(var(--sidebar))',
            foreground: 'hsl(var(--sidebar-foreground))',
            primary: 'hsl(var(--sidebar-primary))',
            'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
            accent: 'hsl(var(--sidebar-accent))',
            'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          },
        },
      },
    },
    plugins: [],
  };

  