import { Navigate, Route, Routes } from "react-router-dom";
import AdminAudit from "./pages/AdminAudit";
import AdminReviews from "./pages/AdminReviews";
import AuthSuccess from "./pages/AuthSuccess";
import BrandCardReference from "./pages/BrandCardReference";
import Home from "./pages/Home";
import Intro from "./pages/Intro";
import Login from "./pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/success" element={<AuthSuccess />} />
      <Route path="/intro" element={<Intro />} />
      <Route path="/brand/cards" element={<BrandCardReference />} />
      <Route path="/admin/audit" element={<AdminAudit />} />
      <Route path="/admin/reviews" element={<AdminReviews />} />
      <Route path="/" element={<Home />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
