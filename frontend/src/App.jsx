import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import SpecConfiguration from './components/SpecConfiguration';
import ExtractionResults from './components/ExtractionResults';
import CanonicalInspector from './components/CanonicalInspector';
import ExtractionProgress from './components/ExtractionProgress';
import { PlayCircle, FileUp, Cpu, BarChart3, ChevronRight } from 'lucide-react';

function App() {
  const [currentStep, setCurrentStep] = useState(1); // 1: Setup, 2: Processing, 3: Results
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
    setCurrentStep(2); // Move to Processing & Logs page

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
      setCurrentStep(3); // Auto-advance to Results Dashboard
    } catch (err) {
      setError(err.message);
      setCurrentStep(1); // Return to setup on failure
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="digital" style={{ backgroundColor: '#f8fafc', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Deloitte Top Header */}
      <header className="dds-header dds-header_inverse" style={{ backgroundColor: '#000000', borderBottom: '3px solid var(--deloitte-green)' }}>
        <div className="dds-header__container" style={{ display: 'flex', width: '100%', maxWidth: '1440px', margin: '0 auto', alignItems: 'center', height: '64px', padding: '0 24px' }}>
          <div className="dds-header__main" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ color: '#ffffff', fontSize: '20px', fontWeight: 800, letterSpacing: '-0.5px' }}>Deloitte.</span>
            <span style={{ color: 'var(--cool-gray-6)', fontSize: '16px' }}>|</span>
            <span style={{ color: '#ffffff', fontSize: '15px', fontWeight: 600 }}>Enterprise Document Understanding</span>
          </div>

          {/* Step Stepper Header Navigation */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button 
              onClick={() => setCurrentStep(1)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '20px',
                border: 'none',
                backgroundColor: currentStep === 1 ? 'var(--accessible-green)' : 'rgba(255,255,255,0.1)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: currentStep === 1 ? 700 : 400,
                cursor: 'pointer'
              }}
            >
              <FileUp size={14} /> 1. Document & Spec Setup
            </button>

            <ChevronRight size={14} style={{ color: 'var(--cool-gray-6)' }} />

            <button 
              onClick={() => loading && setCurrentStep(2)}
              disabled={!loading && !results}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '20px',
                border: 'none',
                backgroundColor: currentStep === 2 ? 'var(--accessible-green)' : 'rgba(255,255,255,0.1)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: currentStep === 2 ? 700 : 400,
                cursor: loading ? 'pointer' : 'default',
                opacity: (!loading && !results) ? 0.5 : 1
              }}
            >
              <Cpu size={14} /> 2. Live Processing
            </button>

            <ChevronRight size={14} style={{ color: 'var(--cool-gray-6)' }} />

            <button 
              onClick={() => results && setCurrentStep(3)}
              disabled={!results}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '20px',
                border: 'none',
                backgroundColor: currentStep === 3 ? 'var(--accessible-green)' : 'rgba(255,255,255,0.1)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: currentStep === 3 ? 700 : 400,
                cursor: results ? 'pointer' : 'default',
                opacity: !results ? 0.5 : 1
              }}
            >
              <BarChart3 size={14} /> 3. Results Dashboard
            </button>
          </div>
        </div>
      </header>

      {/* Main Full-Width Multi-Step Content Area */}
      <main style={{ flex: 1, width: '100%', maxWidth: '1440px', margin: '0 auto', padding: '32px 24px' }}>
        
        {/* STEP 1: Full-Width Document Upload & Target Spec Configuration */}
        {currentStep === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Page Title & Context */}
            <div className="dds-flex" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a', margin: '0 0 4px 0' }}>Step 1: Upload Document & Select Target Fields</h1>
                <p style={{ fontSize: '14px', color: 'var(--cool-gray-9)', margin: 0 }}>
                  Upload an IFRS/Ind AS annual report PDF and select specific target entities from the visual taxonomy builder below.
                </p>
              </div>

              {/* Primary Execute Button Top Action */}
              <button 
                className={`dds-btn dds-btn_primary dds-btn_green ${(!file || loading) ? 'dds-btn_disabled' : ''}`}
                style={{ padding: '14px 28px', fontSize: '15px', fontWeight: 700, borderRadius: '6px', boxShadow: '0 4px 12px rgba(38,137,13,0.25)' }}
                onClick={handleExtract}
                disabled={!file || loading}
              >
                <PlayCircle style={{ marginRight: '8px' }} />
                Execute Spec Extraction
              </button>
            </div>

            {error && (
              <div style={{ padding: '16px 20px', backgroundColor: '#FCE8E6', color: 'var(--red)', borderLeft: '4px solid var(--red)', borderRadius: '6px', fontSize: '14px' }}>
                <strong>Extraction Error:</strong> {error}
              </div>
            )}

            {/* Top Area: Full-Width File Upload Component */}
            <DocumentUpload onFileSelect={setFile} />

            {/* Main Area: Full-Width Target Specification Selector */}
            <SpecConfiguration onSpecChange={setSpec} />

            {/* Bottom Action Bar */}
            <div 
              className="dds-flex" 
              style={{ 
                justify: 'space-between', 
                alignItems: 'center', 
                backgroundColor: '#ffffff', 
                padding: '20px 32px', 
                borderRadius: '8px', 
                border: '1px solid var(--cool-gray-2)',
                boxShadow: '0 4px 16px rgba(0,0,0,0.04)'
              }}
            >
              <div>
                <strong style={{ fontSize: '15px', color: 'var(--black)' }}>Ready to run schema-driven extraction?</strong>
                <span style={{ display: 'block', fontSize: '12px', color: 'var(--cool-gray-9)', marginTop: '2px' }}>
                  File: {file ? file.name : 'No file uploaded yet'} | Spec: {spec.type === 'preset' ? spec.value : 'Custom Interactive Spec'}
                </span>
              </div>

              <button 
                className={`dds-btn dds-btn_primary dds-btn_green ${(!file || loading) ? 'dds-btn_disabled' : ''}`}
                style={{ padding: '14px 32px', fontSize: '15px', fontWeight: 700, borderRadius: '6px', boxShadow: '0 4px 12px rgba(38,137,13,0.25)' }}
                onClick={handleExtract}
                disabled={!file || loading}
              >
                <PlayCircle style={{ marginRight: '8px' }} />
                Execute Custom Spec Extraction
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Full-Width Live Processing & Stage Logs Page */}
        {currentStep === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ textAlign: 'center', marginBottom: '8px' }}>
              <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a', margin: '0 0 4px 0' }}>Step 2: Processing Document & Running LLM Validation</h1>
              <p style={{ fontSize: '14px', color: 'var(--cool-gray-9)', margin: 0 }}>
                Canonicalizing layout, assembling 2D financial grids, and verifying statement candidates with On-Prem Qwen LLM.
              </p>
            </div>

            <ExtractionProgress fileName={file?.name} />
          </div>
        )}

        {/* STEP 3: Full-Width Uncramped Results Dashboard Page */}
        {currentStep === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div className="dds-flex" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a', margin: '0 0 4px 0' }}>Step 3: Extraction Results & Financial Statements Dashboard</h1>
                <p style={{ fontSize: '14px', color: 'var(--cool-gray-9)', margin: 0 }}>
                  Review full-width reconstructed financial statement grids, provenance evidence, and download Excel packages.
                </p>
              </div>

              <button 
                className="dds-btn dds-btn_secondary"
                onClick={() => setCurrentStep(1)}
                style={{ fontSize: '13px', padding: '10px 18px' }}
              >
                &larr; Configure & Extract Another Document
              </button>
            </div>

            <ExtractionResults results={results} onInspect={setInspectDocId} />
          </div>
        )}
      </main>

      {/* Canonical Inspector Modal */}
      {inspectDocId && (
        <CanonicalInspector documentId={inspectDocId} onClose={() => setInspectDocId(null)} />
      )}
    </div>
  );
}

export default App;

