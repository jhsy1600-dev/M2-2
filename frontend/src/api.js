const API_BASE_URL = "http://127.0.0.1:8000";

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const errorMessage =
      data?.detail ||
      data?.message ||
      `${response.status} 오류가 발생했습니다.`;

    const errorObj = new Error(errorMessage);
    errorObj.response = {
      status: response.status,
      data: data,
    };
    throw errorObj;
  }

  return { data };
}

const api = {
  get: (url) =>
    request(url, {
      method: "GET",
    }),

  post: (url, body) =>
    request(url, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  delete: (url) =>
    request(url, {
      method: "DELETE",
    }),
};

export default api;