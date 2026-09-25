import { Outlet } from 'react-router-dom'
import Header from './Header'

import logo1Black from '../css/logo/LOGO1BLACK.png'
import backgroundVideo from '../css/background/BACKGROUND.mp4'

export default function Layout() {
  return (
    <div className="app-shell">

      <video
        className="background-video"
        autoPlay
        muted
        loop
        playsInline
        aria-hidden="true"
      >
        <source src={backgroundVideo} type="video/mp4" />
      </video>

      <div className="background-video-overlay" />

      <Header />

      <main className="page-wrap">
        <Outlet />
      </main>

      <footer className="footer">
        <img
          className="footer-logo"
          src={logo1Black}
          alt="KAYKAYMYDU"
        />

        <p>
          ®&amp;© 2026 Red Velvet - KAYKAY&amp;MYDU. Warning : All Rights Reserved.
          Unauthorized Duplication &amp; Rent is Prohibited.
        </p>
      </footer>

    </div>
  )
}