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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Search and Action Header */}
      <div className="dds-flex" style={{ justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8f9fa', padding: '16px', borderRadius: '4px', border: '1px solid var(--cool-gray-2)' }}>
        <div style={{ position: 'relative', width: '60%' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--cool-gray-9)' }} />
          <input 
            type="text"
            className="dds-input__field"
            placeholder="Search categories, subcategories, or metrics..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '36px', fontSize: '13px', backgroundColor: '#ffffff' }}
          />
        </div>
        <div className="dds-flex" style={{ gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accessible-blue)' }}>
            {totalSelected} Fields Selected
          </span>
          {totalSelected > 0 && (
            <button className="dds-btn dds-btn_secondary" onClick={clearAll} style={{ fontSize: '12px', padding: '4px 10px' }}>
              Clear Selection
            </button>
          )}
        </div>
      </div>

      {/* Category Accordion Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '550px', overflowY: 'auto', paddingRight: '4px' }}>
        {filteredTaxonomy.map(catObj => {
          const selectedCount = catObj.subcategories.filter(sub => isFieldSelected(catObj.category, sub.name)).length;
          const isAllSelected = selectedCount === catObj.subcategories.length && catObj.subcategories.length > 0;
          const isExpanded = expandedCategories[catObj.id] || searchQuery.length > 0;

          return (
            <div key={catObj.id} style={{ border: '1px solid var(--cool-gray-2)', borderRadius: '4px', backgroundColor: '#ffffff', overflow: 'hidden' }}>
              {/* Category Header */}
              <div 
                className="dds-flex" 
                style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', backgroundColor: selectedCount > 0 ? '#f4f9f1' : '#ffffff', cursor: 'pointer', userSelect: 'none', borderBottom: isExpanded ? '1px solid var(--cool-gray-2)' : 'none' }}
                onClick={() => toggleCategoryExpand(catObj.id)}
              >
                <div className="dds-flex" style={{ alignItems: 'center', gap: '12px' }}>
                  {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <strong style={{ fontSize: '14px', color: 'var(--black)' }}>{catObj.category}</strong>
                  <span className={`dds-status-tag ${selectedCount > 0 ? 'dds-status-tag_green' : 'dds-status-tag_gray'}`} style={{ fontSize: '11px' }}>
                    {selectedCount} / {catObj.subcategories.length} selected
                  </span>
                </div>

                <div 
                  className="dds-flex" 
                  style={{ alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--accessible-blue)', fontWeight: 500 }}
                  onClick={(e) => { e.stopPropagation(); toggleAllInCategory(catObj); }}
                >
                  {isAllSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                  {isAllSelected ? 'Deselect All' : 'Select Category'}
                </div>
              </div>

              {/* Subcategories Grid */}
              {isExpanded && (
                <div style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px', backgroundColor: '#fcfcfc' }}>
                  {catObj.subcategories.map(sub => {
                    const checked = isFieldSelected(catObj.category, sub.name);
                    return (
                      <div 
                        key={sub.name}
                        onClick={() => toggleField(catObj, sub)}
                        style={{
                          padding: '12px',
                          borderRadius: '4px',
                          border: checked ? '1.5px solid var(--accessible-green)' : '1px solid var(--cool-gray-2)',
                          backgroundColor: checked ? '#f4f9f1' : '#ffffff',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div className="dds-flex" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div className="dds-flex" style={{ alignItems: 'center', gap: '8px' }}>
                            <input 
                              type="checkbox"
                              checked={checked}
                              onChange={() => {}} // Handled by div click
                              style={{ accentColor: 'var(--deloitte-green)', cursor: 'pointer' }}
                            />
                            <strong style={{ fontSize: '13px', color: 'var(--black)' }}>{sub.name}</strong>
                          </div>
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '2px', backgroundColor: sub.entity_type === 'table' ? '#e8f4f8' : '#f0f0f0', color: sub.entity_type === 'table' ? 'var(--accessible-blue)' : 'var(--cool-gray-9)', fontWeight: 600, textTransform: 'uppercase' }}>
                            {sub.entity_type}
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: '11px', color: 'var(--cool-gray-9)', lineHeight: 1.3 }}>
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
