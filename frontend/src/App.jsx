import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import SpecConfiguration from './components/SpecConfiguration';
import ExtractionResults from './components/ExtractionResults';
import CanonicalInspector from './components/CanonicalInspector';
import ExtractionProgress from './components/ExtractionProgress';
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
        <div className="dds-header__container" style={{ display: 'flex', width: '100%', maxWidth: '1440px', margin: '0 auto', alignItems: 'center' }}>
          <div className="dds-header__main" style={{ display: 'flex', alignItems: 'center' }}>
            <span className="dds-header__project-name" style={{ color: 'var(--accessible-green)', fontWeight: 700 }}>Deloitte Enterprise Document Understanding</span>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ fontSize: '13px', color: 'var(--cool-gray-6)' }}>Canonicalizer + Spec Extraction Engine v2</span>
          </div>
        </div>
      </header>

      <main className="dds-container" style={{ maxWidth: '1440px', margin: '24px auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: '24px', alignItems: 'start' }}>
          
          {/* Left Column: Configuration & Setup */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <DocumentUpload onFileSelect={setFile} />
            <SpecConfiguration onSpecChange={setSpec} />
            
            <button 
              className={`dds-btn dds-btn_primary dds-btn_green ${loading ? 'dds-btn_disabled' : ''}`}
              style={{ width: '100%', padding: '16px', fontSize: '15px', fontWeight: 600, boxShadow: '0 4px 12px rgba(38,137,13,0.2)' }}
              onClick={handleExtract}
              disabled={loading}
            >
              <PlayCircle style={{ marginRight: '8px' }} />
              {loading ? 'Processing Document...' : 'Execute Custom Spec Extraction'}
            </button>

            {error && (
              <div style={{ padding: '16px', backgroundColor: '#FCE8E6', color: 'var(--red)', borderLeft: '4px solid var(--red)', borderRadius: '4px' }}>
                <strong style={{ display: 'block', marginBottom: '4px' }}>Extraction Error:</strong>
                <span style={{ fontSize: '13px', wordBreak: 'break-word' }}>{error}</span>
              </div>
            )}
          </div>

          {/* Right Column: Results & Interactive Workspace */}
          <div>
            {loading ? (
              <ExtractionProgress fileName={file?.name} />
            ) : results ? (
              <ExtractionResults results={results} onInspect={setInspectDocId} />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '500px', backgroundColor: 'var(--white)', border: '2px dashed var(--cool-gray-4)', borderRadius: '8px', color: 'var(--cool-gray-9)' }}>
                <div style={{ textAlign: 'center', maxWidth: '400px', padding: '24px' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--black)', margin: '0 0 8px 0' }}>Ready for Spec Extraction</h3>
                  <p style={{ fontSize: '13px', color: 'var(--cool-gray-9)', margin: 0 }}>
                    Upload an annual report PDF on the left, choose your target fields using the Interactive Taxonomy Builder, and click Execute!
                  </p>
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
}
}

export default App;
