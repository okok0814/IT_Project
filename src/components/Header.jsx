import { NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import logo2Black from "../css/logo/LOGO2BLACK.png";

function Header() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const goHome = () => {
    navigate("/");
    setMenuOpen(false);
  };

  return (
    <header className="topbar">
      <div className="brand-area">
        <button
          className="menu-toggle"
          onClick={() => setMenuOpen((prev) => !prev)}
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
        >
          ▤
        </button>

        <button
          className="brand-name"
          onClick={goHome}
          aria-label="KAYKAYMYDU home"
        >
        
        <img
        className="header-logo" 
        src={logo2Black} 
        alt="KAYKAYMYDU"
        />
        
        </button>
      </div>

      <nav className={`nav-links ${menuOpen ? "open" : ""}`}>
        <NavLink to="/search/image" onClick={() => setMenuOpen(false)}>
          Image
        </NavLink>

        <NavLink to="/search/text" onClick={() => setMenuOpen(false)}>
          Text
        </NavLink>

        <NavLink to="/results" onClick={() => setMenuOpen(false)}>
          Results
        </NavLink>
      </nav>
    </header>
  );
}

export default Header;
