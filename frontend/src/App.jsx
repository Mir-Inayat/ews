import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import SpecConfiguration from './components/SpecConfiguration';
import ExtractionResults from './components/ExtractionResults';
import CanonicalInspector from './components/CanonicalInspector';
import { PlayCircle } from 'lucide-react';

function App() {
  const [file, setFile] = useState(null);
  const [spec, setSpec] = useState({ type: 'preset', value: 'sample_custom_spec.json' });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [inspectDocId, setInspectDocId] = useState(null);
  const [error, setError] = useState(null);

  const handleExtract = async () => {
    if (!file) {
      alert("Please upload a PDF document first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);

    if (spec.type === 'preset') {
      formData.append("spec_id", spec.value);
    } else {
      formData.append("spec_id", "custom");
      formData.append("spec_json", spec.value);
    }

    try {
      const res = await fetch("http://localhost:8080/api/v1/custom-extract", {
        method: "POST",
        body: formData
      });
      
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        throw new Error(text || "Extraction failed");
      }

      if (!res.ok) {
        throw new Error(data.error || "Extraction failed");
      }

      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="digital">
      <header className="dds-header dds-header_inverse">
        <div className="dds-header__container" style={{ display: 'flex', width: '100%', maxWidth: '1400px', margin: '0 auto', alignItems: 'center' }}>
          <div className="dds-header__main" style={{ display: 'flex', alignItems: 'center' }}>
            <span className="dds-header__project-name" style={{ color: 'var(--accessible-green)' }}>Enterprise Document Understanding</span>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ fontSize: '14px', color: 'var(--cool-gray-6)' }}>Product 1 (Canonicalizer) + Product 2 (Custom Spec Engine)</span>
            <div className="dds-user-pic dds-user-pic_sm" style={{ background: 'var(--accessible-green)', color: 'white', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 'bold' }}>JD</div>
          </div>
        </div>
      </header>

      <main className="dds-container">
        <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '24px' }}>
          
          {/* Left Column: Configuration */}
          <div>
            <DocumentUpload onFileSelect={setFile} />
            <SpecConfiguration onSpecChange={setSpec} />
            
            <button 
              className={`dds-btn dds-btn_primary dds-btn_green ${loading ? 'dds-btn_disabled' : ''}`}
              style={{ width: '100%', marginTop: '16px', padding: '16px', fontSize: '16px' }}
              onClick={handleExtract}
              disabled={loading}
            >
              <PlayCircle style={{ marginRight: '8px' }} />
              {loading ? 'Extracting...' : 'Execute Custom Spec Extraction'}
            </button>

            {error && (
              <div className="dds-mt-4" style={{ padding: '16px', backgroundColor: '#FCE8E6', color: 'var(--red)', borderLeft: '4px solid var(--red)', borderRadius: '4px' }}>
                <strong style={{ display: 'block', marginBottom: '4px' }}>Extraction Error:</strong>
                <span style={{ fontSize: '13px', wordBreak: 'break-word' }}>{error}</span>
              </div>
            )}
          </div>

          {/* Right Column: Results */}
          <div>
            {loading ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', flexDirection: 'column', color: 'var(--cool-gray-9)' }}>
                <div style={{ width: '48px', height: '48px', border: '4px solid var(--cool-gray-2)', borderTopColor: 'var(--accessible-green)', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '16px' }}></div>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                <div style={{ fontSize: '18px', fontWeight: 600 }}>Analyzing Document...</div>
                <div style={{ fontSize: '14px', marginTop: '8px' }}>This may take a few minutes for large reports.</div>
              </div>
            ) : results ? (
              <ExtractionResults results={results} onInspect={setInspectDocId} />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', backgroundColor: 'var(--white)', border: '1px dashed var(--cool-gray-4)', borderRadius: '8px', color: 'var(--cool-gray-9)' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>Ready to Extract</div>
                  <div style={{ fontSize: '14px', marginTop: '4px' }}>Upload a report and select a spec to begin.</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {inspectDocId && (
        <CanonicalInspector documentId={inspectDocId} onClose={() => setInspectDocId(null)} />
      )}
    </div>
  );
}

export default App;
