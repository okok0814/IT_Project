import { useNavigate } from "react-router-dom";

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="home-page">
      <section className="hero-panel">
        <div className="floating-disc">✦</div>
        <h1>
          KAYKAYMYDU FASHION DISCOVER
        </h1>
        <div className="hero-actions">
          <button
            className="primary-btn"
            onClick={() => navigate("/search/image")}
          >
            SEARCH BY IMAGE
          </button>
          <button
            className="secondary-btn"
            onClick={() => navigate("/search/text")}
          >
            SEARCH BY TEXT
          </button>
        </div>
      </section>

      <section className="feature-grid">
        <article className="feature-card">
          <span className="feature-index">01</span>
          <h3>IMAGE SEARCH</h3>
          <p>Upload a fashion image to discover visually similar pieces.</p>
        </article>

        <article className="feature-card">
          <span className="feature-index">02</span>
          <h3>TEXT SEARCH</h3>
          <p>
            Describe the piece you want, such as “black shirt”, and explore matching styles.
          </p>
        </article>

        <article className="feature-card">
          <span className="feature-index">03</span>
          <h3>RESULTS</h3>
          <p>
            Explore refined matches, filters and similarity scores in one elegant view.
          </p>
        </article>
      </section>
    </div>
  );
}
