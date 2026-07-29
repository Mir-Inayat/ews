import React, { useState } from 'react';
import { TAXONOMY } from '../data/taxonomyData';
import { ChevronDown, ChevronRight, Search, CheckSquare, Square } from 'lucide-react';

export default function InteractiveFieldSelector({ selectedFields, onSelectionChange }) {
  const [expandedCategories, setExpandedCategories] = useState({ company_info: true, financial_statements: true });
  const [searchQuery, setSearchQuery] = useState('');

  const toggleCategoryExpand = (catId) => {
    setExpandedCategories(prev => ({ ...prev, [catId]: !prev[catId] }));
  };

  const isFieldSelected = (category, subcategory) => {
    const key = `${category}::${subcategory}`;
    return !!selectedFields[key];
  };

  const toggleField = (catObj, subObj) => {
    const key = `${catObj.category}::${subObj.name}`;
    const updated = { ...selectedFields };
    if (updated[key]) {
      delete updated[key];
    } else {
      updated[key] = {
        category: catObj.category,
        subcategory: subObj.name,
        entity_name: subObj.name,
        entity_type: subObj.entity_type,
        description: subObj.description
      };
    }
    onSelectionChange(updated);
  };

  const toggleAllInCategory = (catObj) => {
    const updated = { ...selectedFields };
    const allSelected = catObj.subcategories.every(sub => isFieldSelected(catObj.category, sub.name));

    catObj.subcategories.forEach(sub => {
      const key = `${catObj.category}::${sub.name}`;
      if (allSelected) {
        delete updated[key];
      } else {
        updated[key] = {
          category: catObj.category,
          subcategory: sub.name,
          entity_name: sub.name,
          entity_type: sub.entity_type,
          description: sub.description
        };
      }
    });

    onSelectionChange(updated);
  };

  const clearAll = () => {
    onSelectionChange({});
  };

  const totalSelected = Object.keys(selectedFields).length;

  const filteredTaxonomy = TAXONOMY.filter(catObj => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    if (catObj.category.toLowerCase().includes(q)) return true;
    return catObj.subcategories.some(sub => sub.name.toLowerCase().includes(q) || sub.description.toLowerCase().includes(q));
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Search and Action Toolbar */}
      <div 
        className="dds-flex" 
        style={{ 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          backgroundColor: '#ffffff', 
          padding: '16px 24px', 
          borderRadius: '8px', 
          border: '1px solid var(--cool-gray-2)',
          boxShadow: '0 2px 6px rgba(0,0,0,0.03)'
        }}
      >
        <div style={{ position: 'relative', width: '500px' }}>
          <Search size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--cool-gray-9)' }} />
          <input 
            type="text"
            className="dds-input__field"
            placeholder="Search across 16 categories and 60+ subcategories..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '40px', height: '42px', fontSize: '14px', backgroundColor: '#f8f9fa' }}
          />
        </div>

        <div className="dds-flex" style={{ gap: '16px', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accessible-green)', padding: '6px 14px', backgroundColor: '#f4f9f1', borderRadius: '20px', border: '1px solid #d0e8c5' }}>
            {totalSelected} Fields Selected
          </span>
          {totalSelected > 0 && (
            <button className="dds-btn dds-btn_secondary" onClick={clearAll} style={{ fontSize: '13px', padding: '6px 14px' }}>
              Clear All Selections
            </button>
          )}
        </div>
      </div>

      {/* Spacious 2/3-Column Category Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px', alignItems: 'start' }}>
        {filteredTaxonomy.map(catObj => {
          const selectedCount = catObj.subcategories.filter(sub => isFieldSelected(catObj.category, sub.name)).length;
          const isAllSelected = selectedCount === catObj.subcategories.length && catObj.subcategories.length > 0;
          const isExpanded = expandedCategories[catObj.id] ?? true; // Default expanded for spacious view

          return (
            <div 
              key={catObj.id} 
              style={{ 
                border: selectedCount > 0 ? '1.5px solid var(--accessible-green)' : '1px solid var(--cool-gray-2)', 
                borderRadius: '8px', 
                backgroundColor: '#ffffff', 
                boxShadow: '0 2px 6px rgba(0,0,0,0.02)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              {/* Category Header */}
              <div 
                className="dds-flex" 
                style={{ 
                  justifyContent: 'space-between', 
                  alignItems: 'center', 
                  padding: '14px 18px', 
                  backgroundColor: selectedCount > 0 ? '#f4f9f1' : '#f8f9fa', 
                  cursor: 'pointer', 
                  userSelect: 'none', 
                  borderBottom: '1px solid var(--cool-gray-2)' 
                }}
                onClick={() => toggleCategoryExpand(catObj.id)}
              >
                <div className="dds-flex" style={{ alignItems: 'center', gap: '10px' }}>
                  {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <div>
                    <strong style={{ fontSize: '14px', color: 'var(--black)', display: 'block' }}>{catObj.category}</strong>
                    <span style={{ fontSize: '11px', color: selectedCount > 0 ? 'var(--accessible-green)' : 'var(--cool-gray-9)', fontWeight: selectedCount > 0 ? 600 : 400 }}>
                      {selectedCount} of {catObj.subcategories.length} selected
                    </span>
                  </div>
                </div>

                <button 
                  className="dds-btn dds-btn_secondary"
                  onClick={(e) => { e.stopPropagation(); toggleAllInCategory(catObj); }}
                  style={{ fontSize: '11px', padding: '4px 8px', height: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  {isAllSelected ? <CheckSquare size={14} /> : <Square size={14} />}
                  {isAllSelected ? 'Deselect' : 'Select All'}
                </button>
              </div>

              {/* Subcategories List inside Card */}
              {isExpanded && (
                <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '350px', overflowY: 'auto' }}>
                  {catObj.subcategories.map(sub => {
                    const checked = isFieldSelected(catObj.category, sub.name);
                    return (
                      <div 
                        key={sub.name}
                        onClick={() => toggleField(catObj, sub)}
                        style={{
                          padding: '10px 12px',
                          borderRadius: '6px',
                          border: checked ? '1.5px solid var(--accessible-green)' : '1px solid #e2e8f0',
                          backgroundColor: checked ? '#f4f9f1' : '#ffffff',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                          transition: 'all 0.12s ease'
                        }}
                      >
                        <div className="dds-flex" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                          <div className="dds-flex" style={{ alignItems: 'center', gap: '8px' }}>
                            <input 
                              type="checkbox"
                              checked={checked}
                              onChange={() => {}} // Handled by div click
                              style={{ accentColor: 'var(--deloitte-green)', cursor: 'pointer', width: '15px', height: '15px' }}
                            />
                            <strong style={{ fontSize: '13px', color: 'var(--black)' }}>{sub.name}</strong>
                          </div>
                          <span style={{ fontSize: '9px', padding: '2px 5px', borderRadius: '3px', backgroundColor: sub.entity_type === 'table' ? '#e8f4f8' : '#f1f5f9', color: sub.entity_type === 'table' ? 'var(--accessible-blue)' : 'var(--cool-gray-9)', fontWeight: 700, textTransform: 'uppercase' }}>
                            {sub.entity_type}
                          </span>
                        </div>
                        <p style={{ margin: 0, paddingLeft: '23px', fontSize: '11px', color: 'var(--cool-gray-9)', lineHeight: 1.3 }}>
                          {sub.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
