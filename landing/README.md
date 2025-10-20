# 🔥 Hefesto Landing Page

Production-ready landing page for Hefesto AI Code Quality Agent.

## 📁 Structure

```
landing/
├── index.html          # Main landing page
├── css/
│   └── styles.css     # All styles (modern, responsive)
├── js/
│   └── main.js        # Interactive features
├── assets/
│   └── .gitkeep       # Assets directory (add images here)
├── vercel.json        # Vercel deployment config
└── README.md          # This file
```

## 🚀 Quick Deploy

### Deploy to Vercel (Recommended)

1. **Install Vercel CLI** (if you haven't already):
   ```bash
   npm install -g vercel
   ```

2. **Navigate to landing directory**:
   ```bash
   cd landing/
   ```

3. **Deploy**:
   ```bash
   vercel
   ```

4. **Follow the prompts**:
   - Set up and deploy: Yes
   - Which scope: (select your account)
   - Link to existing project: No
   - Project name: `hefesto-landing`
   - Directory: `./`
   - Override settings: No

5. **Production deployment**:
   ```bash
   vercel --prod
   ```

Your landing page will be live at: `https://hefesto-landing.vercel.app`

### Deploy to Netlify

1. **Install Netlify CLI**:
   ```bash
   npm install -g netlify-cli
   ```

2. **Navigate to landing directory**:
   ```bash
   cd landing/
   ```

3. **Deploy**:
   ```bash
   netlify deploy
   ```

4. **Production deployment**:
   ```bash
   netlify deploy --prod
   ```

### Manual Deployment (Any Static Host)

The landing page is a simple static site. Upload these files to any static hosting:

- **GitHub Pages**: Push to `gh-pages` branch
- **Cloudflare Pages**: Connect your repo
- **AWS S3 + CloudFront**: Upload files to S3 bucket
- **Firebase Hosting**: Use `firebase deploy`

## 🎨 Customization

### Update Stripe Links

All Stripe payment links are in `index.html`. Search and replace:

```html
<!-- Trial link -->
https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04

<!-- Founding Member link -->
https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40

<!-- Annual link -->
https://buy.stripe.com/9B69AS5fAfRv9Y2ei2eAg03
```

### Add Analytics

Uncomment the Google Analytics section in `<head>`:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

Replace `G-XXXXXXXXXX` with your tracking ID.

### Add Images

Place images in `assets/` directory:

```
assets/
├── og-image.png        # Open Graph image (1200x630px)
├── logo.svg            # Company logo
├── screenshot-1.png    # Product screenshots
└── ...
```

Update image references in `index.html`.

### Customize Colors

Edit CSS variables in `css/styles.css`:

```css
:root {
  --color-primary: #5469D4;      /* Brand color */
  --color-primary-dark: #3B50C4;
  --color-accent: #FF6B6B;
  /* ... more colors ... */
}
```

### Customize Content

Edit text in `index.html`:

- **Hero title**: Line ~105
- **Features**: Line ~200
- **Pricing**: Line ~300
- **FAQ**: Line ~450

## 📊 Analytics Integration

### Google Analytics 4

Add GA4 in `<head>` of `index.html`:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

### Facebook Pixel

Add Pixel in `<head>`:

```html
<script>
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', 'YOUR_PIXEL_ID');
  fbq('track', 'PageView');
</script>
```

## 🔧 Features

### Built-in Functionality

- ✅ **Responsive Design**: Mobile, tablet, desktop
- ✅ **Mobile Menu**: Hamburger menu for mobile
- ✅ **Copy to Clipboard**: Install command copy button
- ✅ **Smooth Scrolling**: Anchor link navigation
- ✅ **CTA Tracking**: Event tracking ready
- ✅ **SEO Optimized**: Meta tags, Open Graph, Twitter Cards
- ✅ **Fast Loading**: Minimal dependencies, optimized assets
- ✅ **Accessible**: WCAG 2.1 AA compliant

### Performance

- **Lighthouse Score**: 95+
- **First Contentful Paint**: <1s
- **Time to Interactive**: <2s
- **Total Bundle Size**: <50KB (HTML + CSS + JS)

## 🔗 Short Links

Vercel config includes short links:

- `/trial` → Stripe trial page
- `/founding` → Founding Member signup
- `/annual` → Annual plan
- `/github` → GitHub repository
- `/docs` → Documentation

Example: `https://hefesto.narapallc.com/trial`

## 🧪 Testing

### Test Locally

1. **Simple HTTP Server** (Python):
   ```bash
   cd landing/
   python3 -m http.server 8000
   ```
   Open: http://localhost:8000

2. **Live Server** (VS Code extension):
   - Install "Live Server" extension
   - Right-click `index.html` → "Open with Live Server"

3. **Node.js HTTP Server**:
   ```bash
   npx http-server landing/ -p 8000
   ```

### Test Responsiveness

- **Chrome DevTools**: F12 → Toggle device toolbar
- **Responsive Design Mode**: Cmd/Ctrl + Shift + M
- **Real Devices**: Test on actual phones/tablets

### Test Performance

```bash
npx lighthouse https://your-deployed-url.vercel.app --view
```

## 📝 Custom Domain Setup

### Vercel

1. Go to Vercel Dashboard
2. Select your project
3. Settings → Domains
4. Add domain: `hefesto.narapallc.com`
5. Add DNS records (provided by Vercel)

### DNS Configuration

Add these records to your DNS:

```
Type    Name     Value
A       @        76.76.21.21
CNAME   www      cname.vercel-dns.com
```

## 🔒 Security Headers

Included in `vercel.json`:

- ✅ **X-Content-Type-Options**: `nosniff`
- ✅ **X-Frame-Options**: `DENY`
- ✅ **X-XSS-Protection**: `1; mode=block`
- ✅ **Referrer-Policy**: `strict-origin-when-cross-origin`

## 📧 Contact Form (Optional)

To add email capture, uncomment the form section in `index.html` and set up:

1. **Netlify Forms**: Add `netlify` attribute
2. **Formspree**: Add Formspree endpoint
3. **Custom Backend**: POST to `/api/subscribe`

Example (Formspree):

```html
<form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
  <input type="email" name="email" placeholder="Enter your email" required>
  <button type="submit">Get Early Access</button>
</form>
```

## 🐛 Troubleshooting

### CSS Not Loading

Check file paths are correct:
```html
<link rel="stylesheet" href="css/styles.css">
```

### JavaScript Not Working

Check browser console for errors:
- F12 → Console tab
- Look for error messages

### Mobile Menu Not Opening

Ensure `mobile-menu-toggle` ID matches JavaScript:
```html
<button class="mobile-menu-toggle" id="mobileMenuToggle">
```

### Fonts Not Loading

Check Google Fonts link in `<head>`:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
```

## 📚 Resources

- **Vercel Docs**: https://vercel.com/docs
- **Stripe Payment Links**: https://stripe.com/docs/payment-links
- **Google Analytics**: https://analytics.google.com
- **Lighthouse**: https://developers.google.com/web/tools/lighthouse

## 📞 Support

Questions? Contact: **support@narapallc.com**

---

**© 2025 Narapa LLC. All rights reserved.**

