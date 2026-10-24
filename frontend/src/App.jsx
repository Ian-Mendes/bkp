import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Home from "./pages/Home";
import Login from "./pages/Login";
import InviteAccept from "./pages/InviteAccept";
import Dashboard from "./pages/Dashboard";
import Orders from "./pages/Orders";
import OrderDetail from "./pages/OrderDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/invite/:token" element={<InviteAccept />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/orders" element={<Orders />} />
      <Route path="/orders/:orderId" element={<OrderDetail />} />
    </Routes>
  );
}
