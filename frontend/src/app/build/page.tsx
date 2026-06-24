import Sidebar from '@/components/builder/Sidebar';
import MainContent from '@/components/builder/MainContent';
import styles from './Build.module.css';

export default function BuildPage() {
  return (
    <div className={styles.container}>
      <Sidebar />
      <MainContent />
    </div>
  );
}
