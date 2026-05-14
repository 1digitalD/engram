import React from 'react';
import styles from './ErrorBoundary.module.css';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className={styles.container}>
          <h1 className={styles.heading}>Something went wrong</h1>
          <p className={styles.message}>
            {this.state.error.message}
          </p>
          <button
            className="btn btn-primary"
            onClick={() => { this.setState({ error: null }); window.location.href = '/'; }}
          >
            Reload app
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
