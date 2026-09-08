import React, { useContext } from 'react';
import { AutomationContext } from '../context/AutomationContext';

export default function GlobalPopupModal() {
  const { popupMessage, setPopupMessage } = useContext(AutomationContext);

  if (!popupMessage) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
        <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
          <span className="text-red-500 mr-2">⚠️</span> Atención
        </h2>
        <p className="text-gray-700 mb-6">{popupMessage}</p>
        <div className="flex justify-end">
          <button 
            onClick={() => {
              setPopupMessage(null);
              window.location.reload();
            }}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded transition-colors"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
}
