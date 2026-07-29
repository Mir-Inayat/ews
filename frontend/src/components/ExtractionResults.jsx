import React from 'react';
import { Download } from 'lucide-react';

export default function ExtractionResults({ results, onInspect }) {
  if (!results) return null;

  return (
    <div className="dds-table-block">
      <div className="dds-table-block__header">
        <h3 className="dds-table-block__title">Custom Extraction Results</h3>
        <div className="dds-flex" style={{ gap: '12px' }}>
          <button className="dds-btn dds-btn_secondary" onClick={() => onInspect(results.document_id)}>
            👁️ Inspect Canonical
          </button>
          <a href={`http://localhost:8080/api/v1/download/excel/${results.document_id}`} className="dds-btn dds-btn_primary dds-btn_green" target="_blank" rel="noreferrer">
            <Download size={16} style={{ marginRight: '8px' }} /> Download Excel
          </a>
        </div>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', padding: '16px 24px', backgroundColor: '#f8f9fa', borderBottom: '1px solid var(--cool-gray-2)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--accessible-blue)' }}>{results.summary.fields_found} / {results.summary.total_fields_requested}</div>
          <div style={{ fontSize: '11px', color: 'var(--cool-gray-9)', textTransform: 'uppercase' }}>Fields Found</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--accessible-blue)' }}>{results.summary.completion_rate_pct}%</div>
          <div style={{ fontSize: '11px', color: 'var(--cool-gray-9)', textTransform: 'uppercase' }}>Completion Rate</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--accessible-blue)' }}>{results.summary.canonical_pages}</div>
          <div style={{ fontSize: '11px', color: 'var(--cool-gray-9)', textTransform: 'uppercase' }}>Canonical Pages</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--accessible-blue)' }}>{results.summary.canonical_tables}</div>
          <div style={{ fontSize: '11px', color: 'var(--cool-gray-9)', textTransform: 'uppercase' }}>Canonical Tables</div>
        </div>
      </div>

      <div className="dds-table-block__content" style={{ padding: 0 }}>
        <table className="dds-data-table">
          <thead>
            <tr>
              <th className="dds-data-table__header-cell">Category</th>
              <th className="dds-data-table__header-cell">Entity Name</th>
              <th className="dds-data-table__header-cell">Mode</th>
              <th className="dds-data-table__header-cell">Status</th>
              <th className="dds-data-table__header-cell">Confidence</th>
              <th className="dds-data-table__header-cell">Value / Provenance</th>
            </tr>
          </thead>
          <tbody>
            {results.results.map((f, i) => (
              <tr key={i} className="dds-data-table__row">
                <td className="dds-data-table__cell"><span style={{ fontWeight: 600, fontSize: '12px' }}>{f.category}</span><br/><span style={{ fontSize: '11px', color: 'var(--cool-gray-9)' }}>{f.subcategory}</span></td>
                <td className="dds-data-table__cell"><strong>{f.entity_name}</strong></td>
                <td className="dds-data-table__cell"><span className="dds-status-tag dds-status-tag_gray">{f.extraction_mode}</span></td>
                <td className="dds-data-table__cell">
                  <span className={`dds-status-tag ${f.status === 'FOUND' ? 'dds-status-tag_green' : (f.status === 'ERROR' ? 'dds-status-tag_red' : 'dds-status-tag_gray')}`}>
                    {f.status}
                  </span>
                </td>
                <td className="dds-data-table__cell">{f.confidence ? `${(f.confidence * 100).toFixed(0)}%` : '-'}</td>
                <td className="dds-data-table__cell" style={{ maxWidth: '600px', overflowX: 'auto' }}>
                  {f.status === 'FOUND' && (f.value_raw || f.value_normalized) ? (
                    <>
                      {Array.isArray(f.value_normalized) && f.value_normalized.length > 0 && Array.isArray(f.value_normalized[0]) ? (
                        <div style={{ marginBottom: '16px', maxHeight: '400px', overflowY: 'auto' }}>
                          <table className="dds-data-table" style={{ border: '1px solid var(--cool-gray-2)' }}>
                            <tbody>
                              {f.value_normalized.map((row, rIdx) => (
                                <tr key={rIdx} style={{ borderBottom: '1px solid var(--cool-gray-2)' }}>
                                  {row.map((cell, cIdx) => (
                                    <td key={cIdx} style={{ padding: '8px', fontSize: '12px', borderRight: '1px solid var(--cool-gray-2)', backgroundColor: rIdx === 0 ? 'var(--cool-gray-2)' : 'transparent', fontWeight: rIdx === 0 ? 600 : 400 }}>
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--black)', marginBottom: '8px' }}>
                          {f.value_raw || JSON.stringify(f.value_normalized)}
                        </div>
                      )}
                      {f.provenance && f.provenance.length > 0 && (
                        <div style={{ fontSize: '11px', color: 'var(--cool-gray-9)', borderTop: '1px dashed var(--cool-gray-2)', paddingTop: '4px' }}>
                          <em>{f.explanation}</em>
                        </div>
                      )}
                    </>
                  ) : (
                    <span style={{ color: 'var(--red)', fontSize: '12px' }}>{f.explanation || 'No value found'}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
