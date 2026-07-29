import React, { useEffect, useState } from 'react';
import { X, Search } from 'lucide-react';

export default function CanonicalInspector({ documentId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (documentId) {
      setLoading(true);
      fetch(`http://localhost:8080/api/v1/canonical-document/${encodeURIComponent(documentId)}`)
        .then(res => {
          if (!res.ok) throw new Error('Failed to load canonical document JSON');
          return res.json();
        })
        .then(json => {
          setData(json);
          setLoading(false);
        })
        .catch(err => {
          setError(err.message);
          setLoading(false);
        });
    }
  }, [documentId]);

  return (
    <>
      <div className="dds-modal-overlay show" onClick={onClose}></div>
      <div className="dds-modal" style={{ position: 'fixed', top: '5vh', left: '50%', transform: 'translateX(-50%)', width: '90%', height: '90vh' }}>
        <div className="dds-modal__header">
          <h2 className="dds-modal__title">Canonical Document Inspector v0</h2>
          <button className="dds-modal__close" onClick={onClose}><X /></button>
        </div>
        <div className="dds-modal__body" style={{ flex: 1, backgroundColor: '#1e1e1e', color: '#d4d4d4', margin: 0, padding: 0 }}>
          {loading ? (
            <div style={{ padding: '24px', textAlign: 'center' }}>Loading...</div>
          ) : error ? (
            <div style={{ padding: '24px', color: 'var(--red)' }}>{error}</div>
          ) : (
            <div style={{ padding: '16px', overflowY: 'auto', height: '100%' }}>
              <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '13px' }}>
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
