import ReactDOM from 'react-dom/client';
import '@/index.css';
import './styles.css';
import { App } from './App';

const root = document.getElementById('root');

if (!root) {
  throw new Error('Embed demo root element was not found.');
}

ReactDOM.createRoot(root).render(<App />);
