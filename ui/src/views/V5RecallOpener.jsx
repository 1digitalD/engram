import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRecall } from '../context/RecallContext';

export default function V5RecallOpener() {
  const navigate = useNavigate();
  const { openRecall } = useRecall();

  useEffect(() => {
    openRecall();
    // Return to the previous view so the sheet opens as an overlay.
    navigate(-1);
  }, [openRecall, navigate]);

  return null;
}
